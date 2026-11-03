import pytest
from django.urls import reverse

@pytest.mark.django_db
class TestListasViews:

    def test_pagina_lista_pessoas_carrega_com_sucesso(self, client):
        """Testa se a tela principal de listagem de pessoas abre corretamente"""
        url = reverse('lista-pessoas')
        response = client.get(url)
        assert response.status_code == 200

    def test_pagina_lista_disciplinas_carrega_com_sucesso(self, client):
        """Testa se a tela de listagem de disciplinas abre corretamente"""
        url = reverse('lista-disciplinas')
        response = client.get(url)
        assert response.status_code == 200

    def test_pagina_lista_submodulos_carrega_com_sucesso(self, client):
        """Testa se a tela de listagem de submódulos abre corretamente"""
        url = reverse('lista-submodulos')
        response = client.get(url)
        assert response.status_code == 200

    def test_pagina_lista_modulos_carrega_com_sucesso(self, client):
        """Testa se a tela de listagem de módulos abre corretamente"""
        url = reverse('lista-modulos')
        response = client.get(url)
        assert response.status_code == 200

    def test_pagina_lista_ofertas_modulo_carrega_com_sucesso(self, client):
        """Testa se a tela de listagem de ofertas de módulo abre corretamente"""
        url = reverse('lista-ofertas-modulo')
        response = client.get(url)
        assert response.status_code == 200

    def test_pagina_lista_turmas_carrega_com_sucesso(self, client):
        """Testa se a tela de listagem de turmas abre corretamente"""
        url = reverse('lista-turmas')
        response = client.get(url)
        assert response.status_code == 200

    def test_pagina_lista_atas_carrega_com_sucesso(self, client):
        """Testa se a tela de listagem de atas abre corretamente"""
        url = reverse('lista-atas')
        response = client.get(url)
        assert response.status_code == 200
