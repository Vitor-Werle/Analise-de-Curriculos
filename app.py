import streamlit as st
import os
import pandas as pd
import base64
from io import BytesIO
import tempfile
from pathlib import Path
import time
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from PyPDF2 import PdfReader
import io
import json

# Configuração da página Streamlit
st.set_page_config(
    page_title="AnalisaCV - Análise de Currículos com IA",
    page_icon="📊",
    layout="wide"
)

# Título da aplicação
st.title("📊 AnalisaCV - Análise de Currículos com IA")

# Inicialização de variáveis de sessão
if 'job_description' not in st.session_state:
    st.session_state.job_description = ""
if 'resumes' not in st.session_state:
    st.session_state.resumes = {}
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = {}
if 'selected_candidates' not in st.session_state:
    st.session_state.selected_candidates = []

# Função para extrair texto de arquivos PDF
def extract_text_from_pdf(pdf_file):
    pdf_reader = PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

# Função para configurar a API da Groq
def setup_groq_api():
    # Coloque sua chave API diretamente aqui
    api_key = "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"  # Substitua pelo seu valor real
    
    return ChatGroq(
        api_key=api_key,
        model_name="llama3-70b-8192"
    )

# Função para resumir currículo
def summarize_resume(resume_text, job_description, llm):
    template = """
    Analise este currículo em relação à descrição da vaga. Forneça uma análise detalhada com pontuações (0-10) em cada categoria e um resumo dos pontos fortes e fracos.

    Descrição da Vaga:
    {job_description}

    Currículo:
    {resume_text}

    Responda no seguinte formato JSON:
    {{
        "resumo_geral": "Resumo geral do candidato em relação à vaga (máximo 150 palavras)",
        "pontuacoes": {{
            "experiencia_relevante": [0-10],
            "habilidades_tecnicas": [0-10],
            "formacao_academica": [0-10],
            "soft_skills": [0-10]
        }},
        "pontuacao_total": [0-10],
        "pontos_fortes": ["Lista de 3-5 pontos fortes"],
        "pontos_fracos": ["Lista de 2-3 áreas de melhoria ou pontos fracos"],
        "recomendacao": "Recomendação final (contratar, entrevistar ou rejeitar)"
    }}

    Retorne apenas o JSON, sem explicações adicionais.
    """
    
    prompt = PromptTemplate(
        input_variables=["resume_text", "job_description"],
        template=template
    )
    
    chain = LLMChain(llm=llm, prompt=prompt)
    result = chain.run(resume_text=resume_text, job_description=job_description)
    
    try:
        # Limpar o resultado para garantir que é um JSON válido
        result = result.strip()
        if result.startswith("```json"):
            result = result[7:]
        if result.endswith("```"):
            result = result[:-3]
        
        result_json = json.loads(result)
        return result_json
    except Exception as e:
        st.error(f"Erro ao processar o resultado da análise: {e}")
        return None

# Função para mostrar os resultados da análise
def display_analysis_results(resume_name, analysis):
    if not analysis:
        return
    
    # Pontuação total e recomendação
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Pontuação Total", f"{analysis['pontuacao_total']}/10")
    with col2:
        recommendation = analysis['recomendacao']
        color = "green" if "contratar" in recommendation.lower() else "orange" if "entrevistar" in recommendation.lower() else "red"
        st.markdown(f"<h3 style='color:{color};'>Recomendação: {recommendation}</h3>", unsafe_allow_html=True)
    
    # Resumo geral
    st.subheader("Resumo Geral")
    st.write(analysis['resumo_geral'])
    
    # Pontuações detalhadas
    st.subheader("Pontuações Detalhadas")
    scores = analysis['pontuacoes']
    
    # Criar um gráfico de barras horizontal com as pontuações
    score_data = pd.DataFrame({
        'Categoria': list(scores.keys()),
        'Pontuação': list(scores.values())
    })
    
    st.bar_chart(score_data.set_index('Categoria'))
    
    # Pontos fortes e fracos
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Pontos Fortes")
        for point in analysis['pontos_fortes']:
            st.markdown(f"✅ {point}")
    
    with col2:
        st.subheader("Pontos Fracos")
        for point in analysis['pontos_fracos']:
            st.markdown(f"⚠️ {point}")

# Função para comparar candidatos lado a lado
def compare_candidates(candidates_data):
    # Criar DataFrame com os dados dos candidatos
    compare_data = []
    
    for name, analysis in candidates_data.items():
        row = {
            'Nome': name,
            'Pontuação Total': analysis['pontuacao_total'],
            'Experiência': analysis['pontuacoes']['experiencia_relevante'],
            'Habilidades Técnicas': analysis['pontuacoes']['habilidades_tecnicas'],
            'Formação': analysis['pontuacoes']['formacao_academica'],
            'Soft Skills': analysis['pontuacoes']['soft_skills'],
            'Recomendação': analysis['recomendacao']
        }
        compare_data.append(row)
    
    df = pd.DataFrame(compare_data)
    
    # Ordenar por pontuação total
    df = df.sort_values('Pontuação Total', ascending=False)
    
    return df

# Função para exportar resultados para Excel
def export_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Comparação de Candidatos', index=False)
    
    b64 = base64.b64encode(output.getvalue()).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="analise_candidatos.xlsx">Baixar Relatório Excel</a>'
    return href

# Interface principal
st.sidebar.title("📋 Configurações")

# Descrição da vaga
with st.sidebar.expander("Descrição da Vaga", expanded=True):
    job_description = st.text_area(
        "Cole a descrição da vaga aqui:",
        value=st.session_state.job_description,
        height=300
    )
    if job_description != st.session_state.job_description:
        st.session_state.job_description = job_description

# Upload de currículos
with st.sidebar.expander("Upload de Currículos", expanded=True):
    uploaded_files = st.file_uploader(
        "Faça o upload dos currículos (PDF):",
        type="pdf",
        accept_multiple_files=True
    )
    
    if uploaded_files:
        progress_bar = st.progress(0)
        for i, file in enumerate(uploaded_files):
            resume_name = file.name.split('.')[0]
            
            # Verifica se o currículo já foi carregado
            if resume_name not in st.session_state.resumes:
                # Extrai o texto do PDF
                resume_text = extract_text_from_pdf(file)
                st.session_state.resumes[resume_name] = resume_text
            
            progress_bar.progress((i + 1) / len(uploaded_files))
        
        st.sidebar.success(f"{len(uploaded_files)} currículos carregados com sucesso!")

# Analisar currículos
if st.sidebar.button("Analisar Currículos") and st.session_state.job_description and st.session_state.resumes:
    # Configurar API da Groq
    llm = setup_groq_api()
    
    if llm:
        progress_bar = st.progress(0)
        
        # Analisar cada currículo
        for i, (name, text) in enumerate(st.session_state.resumes.items()):
            if name not in st.session_state.analysis_results:
                st.info(f"Analisando currículo: {name}")
                analysis = summarize_resume(text, st.session_state.job_description, llm)
                
                if analysis:
                    st.session_state.analysis_results[name] = analysis
            
            progress_bar.progress((i + 1) / len(st.session_state.resumes))
        
        st.success("Análise concluída!")

# Aba principal
tab1, tab2, tab3 = st.tabs(["Análise Individual", "Comparação de Candidatos", "Visualização de Currículos"])

with tab1:
    if st.session_state.analysis_results:
        candidate = st.selectbox(
            "Selecione um candidato para análise detalhada:",
            list(st.session_state.analysis_results.keys())
        )
        
        if candidate:
            display_analysis_results(candidate, st.session_state.analysis_results[candidate])
    else:
        st.info("Carregue currículos e faça a análise para ver os resultados.")

with tab2:
    if st.session_state.analysis_results:
        # Seleção de candidatos para comparação
        selected_candidates = st.multiselect(
            "Selecione candidatos para comparação:",
            list(st.session_state.analysis_results.keys()),
            default=list(st.session_state.analysis_results.keys())[:min(3, len(st.session_state.analysis_results))]
        )
        
        if selected_candidates:
            selected_data = {name: st.session_state.analysis_results[name] for name in selected_candidates}
            comparison_df = compare_candidates(selected_data)
            
            # Mostrar tabela de comparação
            st.dataframe(comparison_df, use_container_width=True)
            
            # Exportar para Excel
            st.markdown(export_to_excel(comparison_df), unsafe_allow_html=True)
            
            # Gráfico comparativo das pontuações
            st.subheader("Comparação de Pontuações")
            
            # Preparar dados para o gráfico
            chart_data = pd.DataFrame()
            for name in selected_candidates:
                scores = st.session_state.analysis_results[name]['pontuacoes']
                row = pd.DataFrame({
                    'Candidato': [name] * 4,
                    'Categoria': list(scores.keys()),
                    'Pontuação': list(scores.values())
                })
                chart_data = pd.concat([chart_data, row])
            
            # Criar o gráfico
            chart = pd.pivot_table(
                chart_data, 
                values='Pontuação', 
                index='Categoria', 
                columns='Candidato'
            )
            
            st.bar_chart(chart)
    else:
        st.info("Carregue currículos e faça a análise para comparar candidatos.")

with tab3:
    if st.session_state.resumes:
        resume_to_view = st.selectbox(
            "Selecione um currículo para visualizar:",
            list(st.session_state.resumes.keys())
        )
        
        if resume_to_view:
            st.subheader(f"Currículo: {resume_to_view}")
            st.text_area(
                "Conteúdo do currículo:",
                value=st.session_state.resumes[resume_to_view],
                height=400
            )
    else:
        st.info("Carregue currículos para visualizá-los.")

# Rodapé
st.markdown("---")
st.markdown("AnalisaCV - Desenvolvido com Streamlit, LangChain e Groq")