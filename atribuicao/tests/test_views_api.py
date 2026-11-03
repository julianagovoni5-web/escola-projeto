"""
cadastros/tests/test_views_api.py

Etapa 8 do plano de migração: testes de View/API, cobrindo os endpoints que
já foram reescritos na Etapa 6 (CadastrarPessoaView) mas nunca ganharam teste
próprio, e o BuscarCepView (existente desde a Etapa 2, também sem teste de
View até agora — só o Service tinha teste, em test_buscar_cep.py).
"""
from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from cadastros.models import Funcao, Pessoa, Endereco


def _payload_pessoa(cpf, funcao_id):
    return {
        "nome_completo": "Carlos Teste",
        "cpf": cpf,
        "data_nascimento": "1990-05-10",
        "email": f"{cpf}@x.com",
        "telefone": "12988887777",
        "endereco_cep": "12345000",
        "endereco_logradouro": "Rua das Flores",
        "endereco_numero": "100",
        "endereco_bairro": "Centro",
        "endereco_cidade": "Taubate",
        "endereco_uf": "SP",
        "funcao_id": funcao_id,
        "data_inicio": "2024-02-01",
        "situacao": "ATIVO",
    }


@pytest.mark.django_db
class TestCadastrarPessoaView:

    def test_cadastra_pessoa_via_api_retorna_201(self):
        funcao = Funcao.objects.create(nome="Diretor API", categoria="GESTAO")
        client = APIClient()

        response = client.post(
            reverse("api-cadastrar-pessoa"),
            data=_payload_pessoa("12312312312", funcao.id),
            format="json",
        )

        assert response.status_code == 201
        assert response.data["nome_completo"] == "Carlos Teste"
        assert response.data["funcao"] == "Diretor API"
        assert Pessoa.objects.filter(cpf="12312312312").exists()

    def test_funcao_inexistente_retorna_404(self):
        client = APIClient()

        response = client.post(
            reverse("api-cadastrar-pessoa"),
            data=_payload_pessoa("32132132132", funcao_id=99999),
            format="json",
        )

        assert response.status_code == 404
        assert not Pessoa.objects.filter(cpf="32132132132").exists()

    def test_dados_incompletos_retorna_400(self):
        """Sem passar pelo Service — validação do Serializer já barra antes."""
        funcao = Funcao.objects.create(nome="Secretaria API", categoria="GESTAO")
        client = APIClient()

        payload_incompleto = _payload_pessoa("45645645645", funcao.id)
        del payload_incompleto["cpf"]  # remove um campo obrigatório

        response = client.post(
            reverse("api-cadastrar-pessoa"),
            data=payload_incompleto,
            format="json",
        )

        assert response.status_code == 400

    def test_segunda_funcao_mesmo_cpf_reaproveita_pessoa_via_api(self):
        """Confirma pela API o mesmo comportamento já testado no Service (Etapa 6)."""
        funcao_1 = Funcao.objects.create(nome="Docente API", categoria="DOCENTE")
        funcao_2 = Funcao.objects.create(nome="Diretor API 2", categoria="GESTAO")
        client = APIClient()

        client.post(
            reverse("api-cadastrar-pessoa"),
            data=_payload_pessoa("78978978978", funcao_1.id),
            format="json",
        )
        response = client.post(
            reverse("api-cadastrar-pessoa"),
            data=_payload_pessoa("78978978978", funcao_2.id),
            format="json",
        )

        assert response.status_code == 201
        assert Pessoa.objects.filter(cpf="78978978978").count() == 1


@pytest.mark.django_db
class TestBuscarCepView:

    @patch("cadastros.views.BuscarEnderecoPorCepService")
    def test_busca_cep_retorna_200_com_endereco(self, MockService):
        endereco_mock = Endereco(
            cep="01310100", logradouro="Av. Paulista", numero="",
            complemento="", bairro="Bela Vista", cidade="Sao Paulo", uf="SP",
        )
        MockService.return_value.executar.return_value = endereco_mock

        client = APIClient()
        response = client.get(reverse("api-buscar-cep", kwargs={"cep": "01310100"}))

        assert response.status_code == 200
        assert response.data["logradouro"] == "Av. Paulista"
        assert response.data["cidade"] == "Sao Paulo"

    @patch("cadastros.views.BuscarEnderecoPorCepService")
    def test_busca_cep_invalido_retorna_404(self, MockService):
        MockService.return_value.executar.side_effect = ValueError("CEP não encontrado")

        client = APIClient()
        response = client.get(reverse("api-buscar-cep", kwargs={"cep": "00000000"}))

        assert response.status_code == 404

