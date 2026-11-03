import pytest
from django.urls import reverse
from cadastros.models import Disciplina

@pytest.mark.django_db
class TestDisciplinasViews:

    def test_adicionar_disciplina_via_post(self, client):
        """Testa se a criação de uma nova disciplina funciona quando a soma das horas bate"""
        url = reverse('adicionar-disciplina')
        dados = {
            'nome': 'Matemática Aplicada',
            'sigla': 'MAT',  # Alterado para 3 caracteres
            'carga_horaria_teorica': 40,
            'carga_horaria_pratica': 40,
            'carga_horaria_programa_de_instrucao': 80,
            'ativo': True
        }
        response = client.post(url, dados)
        
        assert response.status_code in [200, 302]
        assert Disciplina.objects.filter(nome='Matemática Aplicada').exists()

    def test_detalhe_disciplina_carrega_com_sucesso(self, client):
        """Testa se a tela de detalhes de uma disciplina abre corretamente"""
        disciplina = Disciplina.objects.create(
            nome='Física Avançada',
            sigla='FIS',  # Alterado para 3 caracteres
            carga_horaria_teorica=30,
            carga_horaria_pratica=30,
            carga_horaria_programa_de_instrucao=60,
            ativo=True
        )
        url = reverse('detalhe-disciplina', kwargs={'pk': disciplina.pk})
        response = client.get(url)
        assert response.status_code == 200
        assert 'Física Avançada' in response.content.decode('utf-8')

    def test_editar_disciplina_salva_alteracoes(self, client):
        """Testa se a alteração dos dados de uma disciplina funciona respeitando as horas"""
        disciplina = Disciplina.objects.create(
            nome='Química',
            sigla='QUI',  # Alterado para 3 caracteres
            carga_horaria_teorica=20,
            carga_horaria_pratica=20,
            carga_horaria_programa_de_instrucao=40,
            ativo=True
        )
        url = reverse('editar-disciplina', kwargs={'pk': disciplina.pk})
        dados_atualizados = {
            'nome': 'Química Orgânica',
            'sigla': 'QUI',  # Alterado para 3 caracteres
            'carga_horaria_teorica': 20,
            'carga_horaria_pratica': 20,
            'carga_horaria_programa_de_instrucao': 40,
            'ativo': True
        }
        response = client.post(url, dados_atualizados)
        
        assert response.status_code in [200, 302]
        disciplina.refresh_from_db()
        assert disciplina.nome == 'Química Orgânica'
