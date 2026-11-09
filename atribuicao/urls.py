from django.urls import path
from .views import (
    GerenciarTurmaView, AdicionarMatriculaTurmaView, EditarMatriculaTurmaView,
    ExcluirMatriculaTurmaView, FinalizarPlanejamentoView, EditarStatusMatriculaView,
    RevisarAprovacaoView, EncerrarTurmaView,
    registro_instrucao_view, horarios_view, relatorios_view, dashboard_gestao_view,
    TreinamentoListView, AuditoriaInternaListView, IndicadoresQualidadeView, AtribuicaoDisciplinaView, contratos_gestao_view
)


urlpatterns = [
    # GERENCIAMENTO DE TURMAS
    path('turmas/<int:pk>/', GerenciarTurmaView.as_view(), name='gerenciar-turma'),
    path('turmas/<int:pk>/alunos/novo/', AdicionarMatriculaTurmaView.as_view(), name='adicionar-matricula-turma'),
    path('matriculas/<int:pk>/editar/', EditarMatriculaTurmaView.as_view(), name='editar-matricula-turma'),
    path('matriculas/<int:pk>/excluir/', ExcluirMatriculaTurmaView.as_view(), name='excluir-matricula-turma'),
    path('matriculas/<int:pk>/editar-status/', EditarStatusMatriculaView.as_view(), name='editar-status-matricula'),
    path('turmas/<int:pk>/finalizar-planejamento/', FinalizarPlanejamentoView.as_view(), name='finalizar-planejamento'),
    path('turmas/<int:pk>/revisar-aprovacao/', RevisarAprovacaoView.as_view(), name='revisar-aprovacao'),
    path('turmas/<int:pk>/encerrar/', EncerrarTurmaView.as_view(), name='encerrar-turma'),
    
    # DIÁRIO DE CLASSE
    path('turmas/registro-instrucao/', registro_instrucao_view, name='registro_instrucao'),
    
    # ROTAS GLOBAIS
    path('horarios/', horarios_view, name='horarios'),
    path('relatorios/', relatorios_view, name='relatorios'),
    path('dashboard/', dashboard_gestao_view, name='dashboard'),
    path('indicadores/', IndicadoresQualidadeView.as_view(), name='indicadores_qualidade'),



    # ATRIBUIÇÃO DE DISCIPLINAS (Duplo mapeamento para salvar o menu dinâmico!)
    path('coordenacao/atribuicao/', AtribuicaoDisciplinaView.as_view(), name='atribuicao-disciplina'),
    path('coordenacao/atribuicao/legacy/', AtribuicaoDisciplinaView.as_view(), name='atribuicao'), # <--- O SEGREDO ESTÁ AQUI!

    # MÓDULO DE QUALIDADE
    path('qualidade/treinamento/', TreinamentoListView.as_view(), name='qualidade-treinamento'),
    path('qualidade/auditoria/', AuditoriaInternaListView.as_view(), name='qualidade-auditoria'),
    path('qualidade/indicadores-qualidade/', IndicadoresQualidadeView.as_view(), name='qualidade-indicadores'),
    path('cadastros/contratos/', contratos_gestao_view, name='contratos_gestao'),
]
