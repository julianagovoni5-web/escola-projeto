import pytest
from cadastros.forms import (
    FormacaoDocenteForm, ExperienciaProfissionalForm, HistoricoVinculoFormalForm,
)
from cadastros.models import VinculoFormal


class TestFormacaoDocenteFormValidacaoParcial:
    """
    Regressão (31/08/2026): uma linha com 'curso' preenchido mas outros campos
    obrigatórios do Model (ex: 'ano_conclusao') vazios passava pelo Form sem
    erro, só falhando no banco com IntegrityError. Corrigido com clean().
    """

    def test_linha_totalmente_vazia_e_valida(self):
        """Linha extra=1 em branco precisa continuar passando, sem erro nenhum."""
        form = FormacaoDocenteForm(data={
            'tipo_formacao': '', 'curso': '', 'entidade': '', 'cidade': '', 'uf': '',
            'ano_conclusao': '',
        })
        assert form.is_valid()

    def test_curso_preenchido_sem_ano_conclusao_e_invalido(self):
        form = FormacaoDocenteForm(data={
            'tipo_formacao': 'GRADUACAO', 'curso': 'Engenharia', 'entidade': 'USP',
            'cidade': 'Sao Paulo', 'uf': 'SP', 'ano_conclusao': '',
        })
        assert not form.is_valid()
        assert 'ano_conclusao' in form.errors

    def test_linha_totalmente_preenchida_e_valida(self):
        form = FormacaoDocenteForm(data={
            'tipo_formacao': 'GRADUACAO', 'curso': 'Engenharia', 'entidade': 'USP',
            'cidade': 'Sao Paulo', 'uf': 'SP', 'ano_conclusao': '2020',
        })
        assert form.is_valid()


class TestExperienciaProfissionalFormValidacaoParcial:

    def test_linha_totalmente_vazia_e_valida(self):
        form = ExperienciaProfissionalForm(data={
            'organizacao': '', 'cargo': '', 'data_inicio': '', 'data_fim': '',
        })
        assert form.is_valid()

    def test_organizacao_preenchida_sem_cargo_e_invalido(self):
        form = ExperienciaProfissionalForm(data={
            'organizacao': 'EMCA', 'cargo': '', 'data_inicio': '2020-01-01', 'data_fim': '',
        })
        assert not form.is_valid()
        assert 'cargo' in form.errors

    def test_organizacao_preenchida_sem_data_inicio_e_invalido(self):
        form = ExperienciaProfissionalForm(data={
            'organizacao': 'EMCA', 'cargo': 'Instrutor', 'data_inicio': '', 'data_fim': '',
        })
        assert not form.is_valid()
        assert 'data_inicio' in form.errors

    def test_linha_totalmente_preenchida_e_valida(self):
        form = ExperienciaProfissionalForm(data={
            'organizacao': 'EMCA', 'cargo': 'Instrutor', 'data_inicio': '2020-01-01', 'data_fim': '',
        })
        assert form.is_valid()


@pytest.mark.django_db
class TestHistoricoVinculoFormalFormValidacaoParcial:
    """ModelChoiceField precisa de um objeto real no banco — daí o django_db."""

    def test_linha_totalmente_vazia_e_valida(self):
        form = HistoricoVinculoFormalForm(data={
            'vinculo_formal': '', 'data_inicio': '', 'data_fim': '',
        })
        assert form.is_valid()

    def test_vinculo_formal_preenchido_sem_data_inicio_e_invalido(self):
        vinculo = VinculoFormal.objects.create(nome="FAPETI Teste")
        form = HistoricoVinculoFormalForm(data={
            'vinculo_formal': str(vinculo.id), 'data_inicio': '', 'data_fim': '',
        })
        assert not form.is_valid()
        assert 'data_inicio' in form.errors

    def test_linha_totalmente_preenchida_e_valida(self):
        vinculo = VinculoFormal.objects.create(nome="FAPETI Teste 2")
        form = HistoricoVinculoFormalForm(data={
            'vinculo_formal': str(vinculo.id), 'data_inicio': '2020-01-01', 'data_fim': '',
        })
        assert form.is_valid()
