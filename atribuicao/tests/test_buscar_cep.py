from unittest.mock import Mock

from cadastros.models import Endereco
from cadastros.services import BuscarEnderecoPorCepService


class TestBuscarEnderecoPorCepService:

    def test_retorna_endereco_usando_cliente_injetado(self):
        cliente_falso = Mock()
        cliente_falso.buscar_endereco.return_value = Endereco(
            cep="01310100", logradouro="Av. Paulista", numero="",
            complemento="", bairro="Bela Vista", cidade="São Paulo", uf="SP",
        )

        service = BuscarEnderecoPorCepService(cliente_cep=cliente_falso)
        resultado = service.executar("01310100")

        assert resultado.cidade == "São Paulo"
        assert resultado.uf == "SP"
        cliente_falso.buscar_endereco.assert_called_once_with("01310100")
