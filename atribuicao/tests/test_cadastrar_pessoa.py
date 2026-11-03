import pytest
from django.core.exceptions import ValidationError
from cadastros.models import (
    Pessoa, Funcao, AtribuicaoFuncao, DadosDiscente, DadosDocente,
    FormacaoDocente, ExperienciaProfissional, HistoricoVinculoFormal,
    PendenciaCadastro, VinculoFormal,
)
from cadastros.services import CadastrarPessoaComFuncaoService


def _dados_pessoa(cpf):
    return {
        "nome_completo": "Maria Teste",
        "cpf": cpf,
        "data_nascimento": "1995-03-20",
        "email": f"{cpf}@x.com",
        "telefone": "11988887777",
        "endereco_cep": "04567000",
        "endereco_logradouro": "Rua Nova",
        "endereco_numero": "200",
        "endereco_complemento": "",
        "endereco_bairro": "Vila X",
        "endereco_cidade": "São Paulo",
        "endereco_uf": "SP",
    }


@pytest.mark.django_db
class TestCadastrarPessoaComFuncaoService:

    def test_cadastra_pessoa_nova_com_funcao(self):
        funcao = Funcao.objects.create(nome="Docente - Instrutor", categoria="DOCENTE")

        pessoa, atribuicao, dados_docente = CadastrarPessoaComFuncaoService().executar(
            dados_pessoa=_dados_pessoa("22233344455"),
            funcao=funcao,
            dados_atribuicao={"data_inicio": "2024-02-01", "situacao": "ATIVO"},
        )

        assert Pessoa.objects.filter(cpf="22233344455").exists()
        assert atribuicao.pessoa == pessoa
        assert atribuicao.funcao == funcao
        assert dados_docente is not None
        assert dados_docente.atribuicao == atribuicao

    def test_reaproveita_pessoa_existente_pelo_cpf(self):
        """Coração da Etapa 6: segunda Função para o mesmo CPF não duplica Pessoa."""
        funcao_1 = Funcao.objects.create(nome="Docente - Instrutor", categoria="DOCENTE")
        funcao_2 = Funcao.objects.create(nome="Coordenador de Curso Aviônicos", categoria="GESTAO")

        pessoa_1, _, _ = CadastrarPessoaComFuncaoService().executar(
            dados_pessoa=_dados_pessoa("33344455566"),
            funcao=funcao_1,
            dados_atribuicao={"data_inicio": "2024-02-01", "situacao": "ATIVO"},
        )
        pessoa_2, atribuicao_2, _ = CadastrarPessoaComFuncaoService().executar(
            dados_pessoa=_dados_pessoa("33344455566"),
            funcao=funcao_2,
            dados_atribuicao={"data_inicio": "2024-03-01", "situacao": "ATIVO"},
        )

        assert pessoa_1.id == pessoa_2.id
        assert Pessoa.objects.filter(cpf="33344455566").count() == 1
        assert pessoa_2.atribuicoes.count() == 2

    def test_rejeita_acumulo_de_funcao_para_discente(self):
        """Regra verificada pela estrutura (DadosDiscente), nunca pelo nome da Funcao."""
        funcao_discente = Funcao.objects.create(nome="Discente - Aluno", categoria="DISCENTE")
        funcao_docente = Funcao.objects.create(nome="Docente - Instrutor", categoria="DOCENTE")

        pessoa = Pessoa.objects.create(**_dados_pessoa("44455566677"))
        atribuicao_discente = AtribuicaoFuncao.objects.create(
            pessoa=pessoa, funcao=funcao_discente,
            data_inicio="2024-02-01", situacao="ATIVO",
        )
        DadosDiscente.objects.create(atribuicao=atribuicao_discente)

        with pytest.raises(ValidationError, match="não pode acumular"):
            CadastrarPessoaComFuncaoService().executar(
                dados_pessoa=_dados_pessoa("44455566677"),
                funcao=funcao_docente,
                dados_atribuicao={"data_inicio": "2024-03-01", "situacao": "ATIVO"},
            )

    def test_nao_cria_segunda_atribuicao_quando_discente_tenta_acumular(self):
        """Confirma que a transação reverte por completo em caso de erro."""
        funcao_discente = Funcao.objects.create(nome="Discente - Aluno", categoria="DISCENTE")
        funcao_docente = Funcao.objects.create(nome="Docente - Instrutor", categoria="DOCENTE")

        pessoa = Pessoa.objects.create(**_dados_pessoa("55566677788"))
        atribuicao_discente = AtribuicaoFuncao.objects.create(
            pessoa=pessoa, funcao=funcao_discente,
            data_inicio="2024-02-01", situacao="ATIVO",
        )
        DadosDiscente.objects.create(atribuicao=atribuicao_discente)

        try:
            CadastrarPessoaComFuncaoService().executar(
                dados_pessoa=_dados_pessoa("55566677788"),
                funcao=funcao_docente,
                dados_atribuicao={"data_inicio": "2024-03-01", "situacao": "ATIVO"},
            )
        except ValidationError:
            pass

        assert pessoa.atribuicoes.count() == 1

    # --- Etapa 7.5: cobertura dos campos repetíveis por categoria ---

    def test_discente_cria_dados_discente_com_campos_corretos(self):
        funcao = Funcao.objects.create(nome="Discente - Aluno", categoria="DISCENTE")

        pessoa, atribuicao, dados_docente = CadastrarPessoaComFuncaoService().executar(
            dados_pessoa=_dados_pessoa("66677788899"),
            funcao=funcao,
            dados_atribuicao={"data_inicio": "2024-02-01", "situacao": "ATIVO"},
            dados_extensao={
                "codigo_matricula_anac": "239.MCELT.25.00115",
                "contato_emergencia_nome": "Joao Teste",
            },
        )

        assert dados_docente is None
        dados_discente = DadosDiscente.objects.get(atribuicao=atribuicao)
        assert dados_discente.codigo_matricula_anac == "239.MCELT.25.00115"
        assert dados_discente.contato_emergencia_nome == "Joao Teste"

    def test_docente_cria_dados_docente_com_multiplas_formacoes(self):
        funcao = Funcao.objects.create(nome="Docente - Instrutor", categoria="DOCENTE")

        pessoa, atribuicao, dados_docente = CadastrarPessoaComFuncaoService().executar(
            dados_pessoa=_dados_pessoa("77788899900"),
            funcao=funcao,
            dados_atribuicao={"data_inicio": "2024-02-01", "situacao": "ATIVO"},
            dados_extensao={},
            formacoes=[
                {
                    "tipo_formacao": "GRADUACAO", "curso": "Engenharia Mecanica",
                    "entidade": "USP", "cidade": "Sao Paulo", "uf": "SP", "ano_conclusao": 2010,
                },
                {
                    "tipo_formacao": "APERFEICOAMENTO_PROFISSIONAL", "curso": "Curso GMP",
                    "entidade": "EMCA", "cidade": "Taubate", "uf": "SP", "ano_conclusao": 2020,
                },
            ],
        )

        assert dados_docente is not None
        assert FormacaoDocente.objects.filter(dados_docente=dados_docente).count() == 2
        assert FormacaoDocente.objects.filter(
            dados_docente=dados_docente, tipo_formacao="GRADUACAO"
        ).exists()

    def test_gestao_cria_multiplas_experiencias_profissionais(self):
        funcao = Funcao.objects.create(nome="Diretor", categoria="GESTAO")

        pessoa, atribuicao, dados_docente = CadastrarPessoaComFuncaoService().executar(
            dados_pessoa=_dados_pessoa("88899900011"),
            funcao=funcao,
            dados_atribuicao={"data_inicio": "2024-02-01", "situacao": "ATIVO"},
            experiencias=[
                {"organizacao": "EMCA", "cargo": "Instrutor", "data_inicio": "2015-01-01", "data_fim": "2020-01-01"},
                {"organizacao": "Outra Empresa", "cargo": "Tecnico", "data_inicio": "2010-01-01", "data_fim": "2014-12-31"},
            ],
        )

        assert dados_docente is None
        assert ExperienciaProfissional.objects.filter(atribuicao=atribuicao).count() == 2

    def test_historico_vinculo_formal_criado_para_docente_e_gestao_nunca_discente(self):
        vinculo_formal = VinculoFormal.objects.create(nome="FAPETI")

        funcao_docente = Funcao.objects.create(nome="Docente - Instrutor 2", categoria="DOCENTE")
        funcao_gestao = Funcao.objects.create(nome="Secretaria 2", categoria="GESTAO")
        funcao_discente = Funcao.objects.create(nome="Discente - Aluno 2", categoria="DISCENTE")

        historico_dados = [{
            "vinculo_formal": vinculo_formal,
            "data_inicio": "2025-01-01",
            "data_fim": None,
        }]

        _, atribuicao_docente, _ = CadastrarPessoaComFuncaoService().executar(
            dados_pessoa=_dados_pessoa("99900011122"),
            funcao=funcao_docente,
            dados_atribuicao={"data_inicio": "2024-02-01", "situacao": "ATIVO"},
            dados_extensao={},
            historico_vinculo_formal=historico_dados,
        )
        assert HistoricoVinculoFormal.objects.filter(atribuicao=atribuicao_docente).count() == 1

        _, atribuicao_gestao, _ = CadastrarPessoaComFuncaoService().executar(
            dados_pessoa=_dados_pessoa("00011122233"),
            funcao=funcao_gestao,
            dados_atribuicao={"data_inicio": "2024-02-01", "situacao": "ATIVO"},
            historico_vinculo_formal=historico_dados,
        )
        assert HistoricoVinculoFormal.objects.filter(atribuicao=atribuicao_gestao).count() == 1

        _, atribuicao_discente, _ = CadastrarPessoaComFuncaoService().executar(
            dados_pessoa=_dados_pessoa("11122233344"),
            funcao=funcao_discente,
            dados_atribuicao={"data_inicio": "2024-02-01", "situacao": "ATIVO"},
            # historico_vinculo_formal passado mesmo assim, mas categoria Discente deve ignorar
            historico_vinculo_formal=historico_dados,
        )
        assert HistoricoVinculoFormal.objects.filter(atribuicao=atribuicao_discente).count() == 0

    def test_pendencia_cadastro_universal_qualquer_categoria(self):
        """PendenciaCadastro roda para qualquer categoria, sem condicional (diferente das demais)."""
        funcao_discente = Funcao.objects.create(nome="Discente - Aluno 3", categoria="DISCENTE")

        pendencias_dados = [{"tipo": "CANAC", "descricao": ""}]

        _, atribuicao, _ = CadastrarPessoaComFuncaoService().executar(
            dados_pessoa=_dados_pessoa("22233344400"),
            funcao=funcao_discente,
            dados_atribuicao={"data_inicio": "2024-02-01", "situacao": "ATIVO"},
            pendencias=pendencias_dados,
        )

        assert PendenciaCadastro.objects.filter(atribuicao=atribuicao, tipo="CANAC").exists()

    # --- Revisão da Etapa 9: validação amigável de duplicidade (encontrado em teste manual) ---

    def test_rejeita_registro_matricula_duplicado_com_mensagem_amigavel(self):
        """RM/RA/CANAC duplicados devem gerar ValidationError amigável, não IntegrityError cru."""
        funcao = Funcao.objects.create(nome="Diretor Teste RM", categoria="GESTAO")

        dados_1 = _dados_pessoa("33344400011")
        dados_1["registro_matricula"] = "RM-DUPLICADO"
        CadastrarPessoaComFuncaoService().executar(
            dados_pessoa=dados_1,
            funcao=funcao,
            dados_atribuicao={"data_inicio": "2024-02-01", "situacao": "ATIVO"},
        )

        dados_2 = _dados_pessoa("44400011122")
        dados_2["registro_matricula"] = "RM-DUPLICADO"

        with pytest.raises(ValidationError, match="RM.*já está em uso"):
            CadastrarPessoaComFuncaoService().executar(
                dados_pessoa=dados_2,
                funcao=funcao,
                dados_atribuicao={"data_inicio": "2024-02-01", "situacao": "ATIVO"},
            )

        assert not Pessoa.objects.filter(cpf="44400011122").exists()

    def test_rejeita_codigo_matricula_anac_duplicado_com_mensagem_amigavel(self):
        """Código de Matrícula ANAC (DadosDiscente) segue a mesma regra de RM/RA/CANAC."""
        funcao = Funcao.objects.create(nome="Discente Teste CMA", categoria="DISCENTE")

        CadastrarPessoaComFuncaoService().executar(
            dados_pessoa=_dados_pessoa("55500011223"),
            funcao=funcao,
            dados_atribuicao={"data_inicio": "2024-02-01", "situacao": "ATIVO"},
            dados_extensao={"codigo_matricula_anac": "239.MCELT.25.00115"},
        )

        with pytest.raises(ValidationError, match="Código de Matrícula ANAC.*já está em uso"):
            CadastrarPessoaComFuncaoService().executar(
                dados_pessoa=_dados_pessoa("66600011224"),
                funcao=funcao,
                dados_atribuicao={"data_inicio": "2024-02-01", "situacao": "ATIVO"},
                dados_extensao={"codigo_matricula_anac": "239.MCELT.25.00115"},
            )

        assert not Pessoa.objects.filter(cpf="66600011224").exists()

