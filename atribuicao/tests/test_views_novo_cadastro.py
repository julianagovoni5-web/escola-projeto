import pytest
from cadastros.models import Funcao, Pessoa, DadosDiscente


def _post_data_discente(cpf, funcao_id, codigo_matricula_anac=""):
    """
    Payload mínimo de um POST válido para NovoCadastroPessoaView, categoria Discente.
    Espelha o payload real capturado num IntegrityError em produção local (31/08/2026),
    incluindo os 4 management_form dos Formsets (Formacao/Experiencia/Historico/Pendencia).
    """
    return {
        "nome_completo": "Aluno Teste",
        "cpf": cpf,
        "data_nascimento": "2005-01-01",
        "email": f"{cpf}@teste.com",
        "telefone": "12988887777",
        "registro_matricula": "",
        "registro_aluno": "",
        "codigo_anac": "",
        "sexo": "",
        "identidade": "",
        "data_emissao_identidade": "",
        "orgao_expedidor_identidade": "",
        "naturalidade": "",
        "uf_naturalidade": "",
        "nacionalidade": "",
        "filiacao_1": "",
        "filiacao_2": "",
        "nivel_instrucao": "",
        "estado_civil": "",
        "raca_cor": "",
        "endereco_cep": "12345000",
        "endereco_logradouro": "Rua Teste",
        "endereco_numero": "100",
        "endereco_complemento": "",
        "endereco_bairro": "Bairro Teste",
        "endereco_cidade": "Taubate",
        "endereco_uf": "SP",
        "funcao": str(funcao_id),
        "data_inicio": "2026-08-31",
        "situacao": "ATIVO",
        "codigo_matricula_anac": codigo_matricula_anac,
        "passaporte": "",
        "autorizacao_permanencia": "",
        "contato_emergencia_nome": "",
        "contato_emergencia_parentesco": "",
        "contato_emergencia_telefone": "",
        "contato_emergencia_endereco": "",
        "responsavel_nome": "",
        "responsavel_endereco": "",
        "responsavel_identidade": "",
        "responsavel_orgao_expedidor": "",
        "responsavel_data_emissao": "",
        "responsavel_qualificacao": "",
        "formacao-TOTAL_FORMS": "1",
        "formacao-INITIAL_FORMS": "0",
        "formacao-MIN_NUM_FORMS": "0",
        "formacao-MAX_NUM_FORMS": "1000",
        "formacao-0-tipo_formacao": "",
        "formacao-0-curso": "",
        "formacao-0-entidade": "",
        "formacao-0-cidade": "",
        "formacao-0-uf": "",
        "formacao-0-ano_conclusao": "",
        "experiencia-TOTAL_FORMS": "1",
        "experiencia-INITIAL_FORMS": "0",
        "experiencia-MIN_NUM_FORMS": "0",
        "experiencia-MAX_NUM_FORMS": "1000",
        "experiencia-0-organizacao": "",
        "experiencia-0-cargo": "",
        "experiencia-0-data_inicio": "",
        "experiencia-0-data_fim": "",
        "historico-TOTAL_FORMS": "1",
        "historico-INITIAL_FORMS": "0",
        "historico-MIN_NUM_FORMS": "0",
        "historico-MAX_NUM_FORMS": "1000",
        "historico-0-vinculo_formal": "",
        "historico-0-data_inicio": "",
        "historico-0-data_fim": "",
        "pendencia-TOTAL_FORMS": "1",
        "pendencia-INITIAL_FORMS": "0",
        "pendencia-MIN_NUM_FORMS": "0",
        "pendencia-MAX_NUM_FORMS": "1000",
        "pendencia-0-tipo": "",
        "pendencia-0-descricao": "",
    }


@pytest.mark.django_db
class TestNovoCadastroPessoaViewCodigoMatriculaAnacVazio:
    """
    Regressão (31/08/2026): NovoCadastroPessoaView montava
    dados_extensao["codigo_matricula_anac"] com dados.get(..., "") em vez de
    `or None`. Como o campo pode legitimamente ficar em branco no primeiro
    cadastro do Discente, dois cadastros seguidos com o campo vazio geravam
    IntegrityError (duas strings vazias colidindo na constraint unique=True),
    em vez de coexistirem como dois NULL. Corrigido em cadastros/views.py.

    Diferente dos testes em test_cadastrar_pessoa.py (que chamam o Service
    diretamente, sempre com dados já corretos), este teste passa pelo Client
    de teste do Django simulando o POST real do formulário HTML — é onde
    o bug de fato vivia, então é a camada certa para testá-lo.
    """

    def test_dois_discentes_com_codigo_matricula_anac_em_branco_nao_colidem(self, client):
        funcao = Funcao.objects.create(nome="Discente Teste View", categoria="DISCENTE")

        resposta_1 = client.post(
            "/cadastros/novo/", data=_post_data_discente("12312312300", funcao.id)
        )
        resposta_2 = client.post(
            "/cadastros/novo/", data=_post_data_discente("32132132100", funcao.id)
        )

        # 302 = redirect de sucesso. Se o bug tivesse voltado, a segunda
        # chamada devolveria 500 (IntegrityError), não 302.
        assert resposta_1.status_code == 302
        assert resposta_2.status_code == 302
        assert Pessoa.objects.filter(cpf="12312312300").exists()
        assert Pessoa.objects.filter(cpf="32132132100").exists()
        assert DadosDiscente.objects.filter(
            atribuicao__pessoa__cpf="12312312300", codigo_matricula_anac__isnull=True
        ).exists()
        assert DadosDiscente.objects.filter(
            atribuicao__pessoa__cpf="32132132100", codigo_matricula_anac__isnull=True
        ).exists()
