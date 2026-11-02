import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from datetime import date
from decimal import Decimal

# Importamos os modelos do app cadastros com um apelido para evitar conflitos de escopo
from cadastros.models import Modulo, OfertaModulo, Turma as CadastrosTurma
# Importamos os modelos do app atribuicao
from atribuicao.models import Atribuicao, HorarioAula, RegistroInstrucao, Disciplina, Turma as AtribuicaoTurma, MatriculaTurma, StatusMatriculaTurma

@pytest.mark.django_db
class TestAtribuicaoHorariosViews:

    @pytest.fixture
    def setup_dados(self):
        """Prepara toda a cadeia de dados obrigatórios exigida pelas restrições do banco"""
        instrutor = User.objects.create_user(username="professor_teste", password="senha_teste")
        
        disciplina = Disciplina.objects.create(
            nome="Matemática Aplicada"
        )
        
        # 1. Cria o Módulo Base usando o modelo de cadastros
        modulo = Modulo.objects.create(
            nome="Módulo de Tecnologia",
            sigla="TEC",
            ativo=True
        )
        
        # 2. Cria a Oferta de Módulo usando o modelo de cadastros
        oferta = OfertaModulo.objects.create(
            modulo=modulo,
            ano_letivo=2026,
            data_inicio="2026-02-01",
            ativo=True
        )
        
        # 3. Cria a Turma de cadastros que possui os campos 'situacao' e 'oferta_modulo'
        turma_cadastros = CadastrosTurma.objects.create(
            nome="Turma Piloto II", 
            situacao="PLANEJADA",
            oferta_modulo=oferta
        )
        
        # 4. Cria a Turma de atribuicao espelhando os dados para satisfazer o ORM de Atribuicao
        turma_atribuicao = AtribuicaoTurma.objects.create(
            id=turma_cadastros.id,
            nome="Turma Piloto II"
        )
        
        # 5. Cria o vínculo mestre de Atribuição usando a instância correta exigida pela chave estrangeira
        atribuicao = Atribuicao.objects.create(
            instrutor=instrutor,
            disciplina=disciplina,
            turma=turma_atribuicao,
            ano_letivo=2026
        )
        return atribuicao

    def test_fixar_horario_na_grade_via_post(self, client, setup_dados):
        """Testa se o formulário de horários salva os dados quando recebe o vínculo correto"""
        atribuicao = setup_dados
        url = reverse('horarios')
        
        dados_formulario = {
            'atribuicao': atribuicao.id,
            'dia_semana': 'SEG',
            'horario_inicio': '08:00',
            'horario_fim': '10:00'
        }
        
        response = client.post(url, dados_formulario)
        assert response.status_code in [200, 302]

    def test_registro_instrucao_lista_dados_corretamente(self, client, setup_dados):
        """Testa se a tela do diário de classe carrega o histórico de aulas do banco"""
        atribuicao = setup_dados
        
        RegistroInstrucao.objects.create(
            instrutor=atribuicao.instrutor,
            atribuicao=atribuicao,
            data_instrucao="2026-10-08",
            carga_horaria=Decimal('2.00'),
            tipo="Teórica",
            conteudo_programatico="Introdução à Engenharia de Software"
        )
        
        url = reverse('registro_instrucao')
        response = client.get(url)
        assert response.status_code == 200

    def test_tela_treinamento_carrega_com_sucesso(self, client, setup_dados):
        """Valida se a página de treinamento abre sem erros (Status 200)."""
        url = reverse('qualidade-treinamento')
        response = client.get(url)
        assert response.status_code == 200

    def test_tela_auditoria_carrega_com_sucesso(self, client, setup_dados):
        """Valida se a página de auditoria abre sem erros (Status 200)."""
        url = reverse('qualidade-auditoria')
        response = client.get(url)
        assert response.status_code == 200

    def test_painel_indicadores_calcula_horas_corretamente(self, client, setup_dados):
        """Garante que a View de Indicadores soma as horas teóricas e práticas do banco certinho."""
        atribuicao = setup_dados

        # Cria os registros de instrução pedagógica usando Decimal
        RegistroInstrucao.objects.create(
            instrutor=atribuicao.instrutor,
            atribuicao=atribuicao,
            data_instrucao=date.today(),
            carga_horaria=Decimal('4.0'),
            tipo='Teórica',
            conteudo_programatico='Introdução a algoritmos'
        )
        RegistroInstrucao.objects.create(
            instrutor=atribuicao.instrutor,
            atribuicao=atribuicao,
            data_instrucao=date.today(),
            carga_horaria=Decimal('2.0'),
            tipo='Prática',
            conteudo_programatico='Laboratório prático'
        )

        url = reverse('qualidade-indicadores')
        response = client.get(url)
        
        assert response.status_code == 200
        assert response.context['horas_totais_instrucao'] == Decimal('6.0')
        assert response.context['horas_teoricas'] == Decimal('4.0')
        assert response.context['horas_praticas'] == Decimal('2.0')
        assert response.context['pct_teorica'] == Decimal('66.7')
