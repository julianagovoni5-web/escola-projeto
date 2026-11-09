"""
cadastros/forms.py

(ver documentação completa no cabeçalho de views.py/docs do projeto)

`data_nascimento` (CadastrarPessoaForm/EditarPessoaForm):
- `min` fixo em 1900-01-01, `max` calculado dinamicamente como a data de HOJE
  a cada instância do Form (não um valor fixo como "2070-12-31") — trava no
  próprio navegador contra ano digitado errado (bug real de teste manual em
  02/09/2026, "12121-12-03") e contra data de nascimento no futuro.
- `clean_data_nascimento()` é a validação AUTORITATIVA (o `max` do HTML é só
  uma trava de navegador, sempre contornável) — rejeita Data de Nascimento
  igual a hoje ou no futuro, com uma mensagem de erro clara. Regra confirmada
  em 02/09/2026: ninguém nasce no futuro, então essa combinação é sempre
  inválida, não uma advertência.

Passaporte/Autorização de Permanência (03/09/2026): campos de Pessoa desde a
auditoria de campos FE 007/FE 008/FOP 402 — visíveis na Identificação Ampliada,
para qualquer categoria (Docente também usa essa documentação, não é exclusiva
de Discente).
"""

from datetime import date

from django import forms
from django.db.models import Q

from .models import (
    Funcao, VinculoFormal, TipoFormacaoDocente, TipoPendencia,
    Sexo, EstadoCivil, RacaCor, FormacaoDocente, HistoricoVinculoFormal,
    ExperienciaProfissional, PendenciaCadastro, AtribuicaoFuncao,
    RequisitoContratacao, Pessoa, Disciplina, ConteudoProgramatico,
    SubModulo, SubModuloDisciplina, Modulo, ModuloSubModulo,
    OfertaModulo, Turma, Ata, AtaPessoa,
)


def _validar_data_nascimento_nao_futura(valor):
    """
    Compartilhada por CadastrarPessoaForm e EditarPessoaForm — Data de
    Nascimento igual a hoje ou no futuro é sempre inválida (ninguém nasce
    no futuro). Levanta ValidationError se a regra for violada.
    """
    if valor and valor >= date.today():
        raise forms.ValidationError(
            "Data de nascimento inválida: não pode ser hoje nem uma data futura."
        )
    return valor


class CadastrarPessoaForm(forms.Form):
    # --- Pessoa: dados básicos ---
    nome_completo = forms.CharField(max_length=200, label="Nome completo")
    cpf = forms.CharField(max_length=11, label="CPF")
    data_nascimento = forms.DateField(
        label="Data de nascimento",
        widget=forms.DateInput(attrs={'type': 'date', 'min': '1900-01-01'})
    )
    email = forms.EmailField(label="E-mail")
    telefone = forms.CharField(max_length=20, label="Telefone")

    # --- Pessoa: identificadores específicos ---
    registro_matricula = forms.CharField(max_length=20, required=False, label="RM")
    registro_aluno = forms.CharField(max_length=20, required=False, label="RA")
    codigo_anac = forms.CharField(max_length=20, required=False, label="CANAC")

    # --- Pessoa: identificação ampliada (FE 007 / FE 008) ---
    sexo = forms.ChoiceField(choices=[('', '---------')] + list(Sexo.choices), required=False, label="Sexo")
    identidade = forms.CharField(max_length=20, required=False, label="Identidade (RG)")
    data_emissao_identidade = forms.DateField(
        required=False, label="Data de emissão", widget=forms.DateInput(attrs={'type': 'date'})
    )
    orgao_expedidor_identidade = forms.CharField(max_length=20, required=False, label="Órgão expedidor")
    naturalidade = forms.CharField(max_length=100, required=False, label="Naturalidade")
    uf_naturalidade = forms.CharField(max_length=2, required=False, label="UF de naturalidade")
    nacionalidade = forms.CharField(max_length=100, required=False, label="Nacionalidade")
    filiacao_1 = forms.CharField(max_length=200, required=False, label="Filiação 1")
    filiacao_2 = forms.CharField(max_length=200, required=False, label="Filiação 2")
    nivel_instrucao = forms.CharField(max_length=100, required=False, label="Nível de instrução")
    estado_civil = forms.ChoiceField(choices=[('', '---------')] + list(EstadoCivil.choices), required=False, label="Estado civil")
    raca_cor = forms.ChoiceField(choices=[('', '---------')] + list(RacaCor.choices), required=False, label="Raça/Cor")

    # --- Pessoa: Título de Eleitor / E-mail 2 / Telefone 2 / Passaporte (aprovados
    # na auditoria de campos de 03/09/2026 — ver docs/28) ---
    titulo_eleitor = forms.CharField(max_length=12, required=False, label="Título de Eleitor")
    zona_eleitoral = forms.CharField(max_length=3, required=False, label="Zona Eleitoral")
    secao_eleitoral = forms.CharField(max_length=4, required=False, label="Seção Eleitoral")
    email_2 = forms.EmailField(required=False, label="E-mail 2")
    telefone_2 = forms.CharField(max_length=20, required=False, label="Telefone 2 / Celular")

    # Passaporte/Autorização de Permanência: campo de Pessoa desde 03/09/2026 (visível
    # para qualquer categoria na Identificação Ampliada, não só Discente).
    passaporte = forms.CharField(max_length=20, required=False, label="Nº do Passaporte")
    autorizacao_permanencia = forms.CharField(
        max_length=50, required=False, label="Autorização de Permanência"
    )

    # --- Pessoa: endereço ---
    endereco_cep = forms.CharField(max_length=8, label="CEP")
    endereco_logradouro = forms.CharField(max_length=200, label="Logradouro")
    endereco_numero = forms.CharField(max_length=10, label="Numero")
    endereco_complemento = forms.CharField(max_length=100, required=False, label="Complemento")
    endereco_bairro = forms.CharField(max_length=100, label="Bairro")
    endereco_cidade = forms.CharField(max_length=100, label="Cidade")
    endereco_uf = forms.CharField(max_length=2, label="UF")

    # --- Funcao / AtribuicaoFuncao ---
    funcao = forms.ModelChoiceField(queryset=Funcao.objects.all(), label="Funcao")
    data_inicio = forms.DateField(
        label="Data de inicio", widget=forms.DateInput(attrs={'type': 'date'})
    )
    situacao = forms.ChoiceField(
        choices=[('ATIVO', 'Ativo'), ('INATIVO', 'Inativo')],
        initial="ATIVO", label="Situacao",
        help_text="Sempre Ativo no cadastro inicial — o campo existe aqui só para "
                   "compatibilidade com AtribuicaoFuncao.situacao (docs/37)."
    )

    # --- AtribuicaoFuncao: Requisitos de Contratação (RBAC 141), todos exceto
    # Discente. Coletados já no cadastro inicial (decisão de 02/09/2026).
    requisito_contratacao = forms.ChoiceField(
        choices=RequisitoContratacao.choices, required=False,
        widget=forms.RadioSelect(), label="Requisito de Contratação"
    )
    documento_comprobatorio = forms.CharField(
        max_length=200, required=False, label="Documento comprobatório"
    )

    # --- DadosDiscente (só relevante quando Funcao.categoria == DISCENTE) ---
    codigo_matricula_anac = forms.CharField(
        max_length=20, required=False, label="Código de Matrícula ANAC"
    )
    contato_emergencia_nome = forms.CharField(
        max_length=200, required=False, label="Contato de emergência - Nome"
    )
    contato_emergencia_parentesco = forms.CharField(
        max_length=50, required=False, label="Contato de emergência - Parentesco"
    )
    contato_emergencia_telefone = forms.CharField(
        max_length=20, required=False, label="Contato de emergência - Telefone"
    )
    contato_emergencia_endereco = forms.CharField(
        max_length=300, required=False, label="Contato de emergência - Endereço"
    )
    responsavel_nome = forms.CharField(
        max_length=200, required=False, label="Responsável legal - Nome"
    )
    responsavel_endereco = forms.CharField(
        max_length=300, required=False, label="Responsável legal - Endereço"
    )
    responsavel_identidade = forms.CharField(
        max_length=20, required=False, label="Responsável legal - Identidade"
    )
    responsavel_orgao_expedidor = forms.CharField(
        max_length=20, required=False, label="Responsável legal - Órgão expedidor"
    )
    responsavel_data_emissao = forms.DateField(
        required=False, label="Responsável legal - Data de emissão",
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    responsavel_qualificacao = forms.CharField(
        max_length=50, required=False, label="Responsável legal - Qualificação (pai/mãe/tutor)"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 'max' calculado a cada instância (não um valor fixo) — sempre a
        # data de hoje, real, no momento em que o formulário é exibido.
        self.fields['data_nascimento'].widget.attrs['max'] = date.today().isoformat()
        
        from django.db.models import Q
        self.fields['funcao'].queryset = Funcao.objects.filter(
            Q(nome__icontains='docente') | 
            Q(nome__icontains='discente') | 
            Q(nome__icontains='gestão') |
            Q(nome__icontains='gestao') |
            Q(nome__icontains='aluno')
        ).order_by('nome')
    
    def clean_data_nascimento(self):
        return _validar_data_nascimento_nao_futura(self.cleaned_data.get('data_nascimento'))


class FormacaoDocenteForm(forms.Form):
    """1 linha de Graduação/Formação Profissional/Aperfeiçoamento (FE 008, seções 3-5)."""
    tipo_formacao = forms.ChoiceField(
        choices=[('', '---------')] + list(TipoFormacaoDocente.choices),
        required=False, label="Tipo"
    )
    curso = forms.CharField(max_length=200, required=False, label="Curso")
    entidade = forms.CharField(max_length=200, required=False, label="Entidade")
    cidade = forms.CharField(max_length=100, required=False, label="Cidade")
    uf = forms.CharField(max_length=2, required=False, label="UF")
    ano_conclusao = forms.IntegerField(required=False, label="Ano de conclusão")

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('curso'):
            campos_obrigatorios = ['tipo_formacao', 'entidade', 'cidade', 'uf', 'ano_conclusao']
            for campo in campos_obrigatorios:
                if not cleaned_data.get(campo):
                    self.add_error(campo, "Obrigatório quando o Curso é preenchido.")
        return cleaned_data


class ExperienciaProfissionalForm(forms.Form):
    """1 linha de Experiência Profissional (FOP 402, só categoria Gestão), usada só no cadastro INICIAL (Formset)."""
    organizacao = forms.CharField(max_length=200, required=False, label="Organização")
    cargo = forms.CharField(max_length=100, required=False, label="Cargo")
    data_inicio = forms.DateField(
        required=False, label="Data de início", widget=forms.DateInput(attrs={'type': 'date'})
    )
    data_fim = forms.DateField(
        required=False, label="Data de fim", widget=forms.DateInput(attrs={'type': 'date'})
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('organizacao'):
            campos_obrigatorios = ['cargo', 'data_inicio']
            for campo in campos_obrigatorios:
                if not cleaned_data.get(campo):
                    self.add_error(campo, "Obrigatório quando a Organização é preenchida.")
        return cleaned_data


class HistoricoVinculoFormalForm(forms.Form):
    """1 linha de Vínculo Formal (Docente ou Gestão — nunca Discente), usada só no cadastro INICIAL (Formset)."""
    
    # 1. PASSAMOS O QUERYSET DO PROPRIO MODELO PARA MATAR O TYPEERROR DE UMA VEZ POR TODAS:
    vinculo_formal = forms.ModelChoiceField(
        queryset=VinculoFormal.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Vínculo Formal"
    )
    
    data_inicio = forms.DateField(
        required=False, label="Data de início", widget=forms.DateInput(attrs={'type': 'date'})
    )
    data_fim = forms.DateField(
        required=False, label="Data de fim", widget=forms.DateInput(attrs={'type': 'date'})
    )

    # 2. SOBRESCREVEMOS AS OPÇÕES NA INICIALIZAÇÃO PARA DEIXAR APENAS DOCENTE E GESTÃO VISÍVEIS:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vinculo_formal'].choices = [
            ('', '---------'),
            ('docente', 'Docente'),
            ('gestao', 'Gestão'),
        ]

    def clean(self):
        cleaned_data = super().clean()
        vinculo_escolhido = cleaned_data.get('vinculo_formal')
        
        if vinculo_escolhido and not cleaned_data.get('data_inicio'):
            self.add_error('data_inicio', "Obrigatório quando o Vínculo Formal é preenchido.")
            
        # 3. TRADUÇÃO DE INSTÂNCIA: Garante compatibilidade relacional com o Service
        if vinculo_escolhido:
            # Se for string, busca o objeto real correspondente
            if isinstance(vinculo_escolhido, str):
                instancia = VinculoFormal.objects.filter(tipo_vinculo__icontains=vinculo_escolhido).first()
                if not instancia:
                    instancia = VinculoFormal.objects.first()
                cleaned_data['vinculo_formal'] = instancia
            
        return cleaned_data


class PendenciaCadastroForm(forms.Form):
    """1 linha de Pendência de documentação — universal, qualquer categoria."""
    tipo = forms.ChoiceField(
        choices=[('', '---------')] + list(TipoPendencia.choices),
        required=False, label="Tipo"
    )
    descricao = forms.CharField(
        max_length=200, required=False, label="Descrição (detalhe, usar sobretudo em 'Outro')"
    )


class EditarPessoaForm(forms.ModelForm):
    """
    Edita os campos COMUNS da Pessoa (identificação + endereço) — qualquer
    categoria. 'cpf' fora (imutável), Função fora (item futuro), campos de
    DadosDiscente fora (Discente ainda sem CRUD próprio). Pessoa nunca é
    excluída — só Create/Read/Update.
    """
    class Meta:
        model = Pessoa
        fields = [
            'nome_completo', 'data_nascimento', 'email', 'email_2', 'telefone', 'telefone_2',
            'registro_matricula', 'registro_aluno', 'codigo_anac',
            'sexo', 'identidade', 'data_emissao_identidade', 'orgao_expedidor_identidade',
            'naturalidade', 'uf_naturalidade', 'nacionalidade',
            'filiacao_1', 'filiacao_2', 'nivel_instrucao', 'estado_civil', 'raca_cor',
            'titulo_eleitor', 'zona_eleitoral', 'secao_eleitoral',
            'passaporte', 'autorizacao_permanencia',
            'endereco_cep', 'endereco_logradouro', 'endereco_numero', 'endereco_complemento',
            'endereco_bairro', 'endereco_cidade', 'endereco_uf',
        ]
        widgets = {
            'data_nascimento': forms.DateInput(attrs={'type': 'date', 'min': '1900-01-01'}),
            'data_emissao_identidade': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_nascimento'].widget.attrs['max'] = date.today().isoformat()

    def clean_data_nascimento(self):
        return _validar_data_nascimento_nao_futura(self.cleaned_data.get('data_nascimento'))


class FormacaoDocenteModelForm(forms.ModelForm):
    """ModelForm para o CRUD independente de FormacaoDocente (Create/Update)."""
    class Meta:
        model = FormacaoDocente
        fields = ['tipo_formacao', 'curso', 'entidade', 'cidade', 'uf', 'ano_conclusao']


_WIDGET_OBSERVACAO = forms.Textarea(attrs={
    'rows': 3,
    'style': 'width:100%; box-sizing:border-box;',
})


class HistoricoVinculoFormalModelForm(forms.ModelForm):
    """ModelForm para adicionar um NOVO período de Vínculo Formal a uma AtribuicaoFuncao já existente."""
    class Meta:
        model = HistoricoVinculoFormal
        fields = ['vinculo_formal', 'data_inicio', 'data_fim', 'observacao']
        widgets = {
            'data_inicio': forms.DateInput(attrs={'type': 'date'}),
            'data_fim': forms.DateInput(attrs={'type': 'date'}),
            'observacao': _WIDGET_OBSERVACAO,
        }


class EncerrarHistoricoVinculoFormalForm(forms.ModelForm):
    """ModelForm restrito para ENCERRAR um período de Vínculo Formal já existente — nunca Delete."""
    class Meta:
        model = HistoricoVinculoFormal
        fields = ['data_fim', 'observacao']
        widgets = {
            'data_fim': forms.DateInput(attrs={'type': 'date'}),
            'observacao': _WIDGET_OBSERVACAO,
        }


class ExperienciaProfissionalModelForm(forms.ModelForm):
    """ModelForm para o CRUD independente de ExperienciaProfissional (Create/Update/Delete)."""
    class Meta:
        model = ExperienciaProfissional
        fields = ['organizacao', 'cargo', 'data_inicio', 'data_fim']
        widgets = {
            'data_inicio': forms.DateInput(attrs={'type': 'date'}),
            'data_fim': forms.DateInput(attrs={'type': 'date'}),
        }


class PendenciaCadastroModelForm(forms.ModelForm):
    """ModelForm para CRIAR uma nova PendenciaCadastro — só 'tipo' e 'descricao'."""
    class Meta:
        model = PendenciaCadastro
        fields = ['tipo', 'descricao']


class EditarPendenciaCadastroForm(forms.ModelForm):
    """ModelForm para EDITAR uma PendenciaCadastro já existente, incluindo marcar como resolvida."""
    class Meta:
        model = PendenciaCadastro
        fields = ['tipo', 'descricao', 'resolvida']


class EditarRequisitoContratacaoForm(forms.ModelForm):
    """
    Edita os Requisitos de Contratação (RBAC 141) de uma AtribuicaoFuncao já
    existente — Docente ou Gestão. Usado fora do cadastro inicial, para
    corrigir/completar depois pela tela de detalhe.
    """
    class Meta:
        model = AtribuicaoFuncao
        fields = ['requisito_contratacao', 'documento_comprobatorio']
        widgets = {
            'requisito_contratacao': forms.RadioSelect(),
        }


class DisciplinaModelForm(forms.ModelForm):
    """
    ModelForm para Criar/Editar Disciplina (CRU — sem Delete, ver docs/33).
    'ativo' fica de fora de propósito: o toggle Ativo/Inativo é uma ação própria
    (ToggleAtivoDisciplinaView), separada da edição normal dos dados da Disciplina
    — mesmo raciocínio já aplicado a AtribuicaoFuncao (situação não se mistura
    com edição de dados comuns).

    A validação de conformidade com o Programa de Instrução (Disciplina.clean())
    dispara automaticamente aqui — ModelForm.is_valid() chama instance.full_clean(),
    que inclui clean(). Mesma trava que já funciona no Admin, sem duplicar código.
    """
    class Meta:
        model = Disciplina
        fields = [
            'nome', 'sigla',
            'carga_horaria_programa_de_instrucao', 'carga_horaria_teorica', 'carga_horaria_pratica',
        ]


class DisciplinaToggleAtivoForm(forms.ModelForm):
    """
    Sem campos próprios — só inverte 'ativo' ao salvar. Usado pela tela de
    confirmação (botão simples + confirmação), nunca editável diretamente.
    """
    class Meta:
        model = Disciplina
        fields = []

    def save(self, commit=True):
        self.instance.ativo = not self.instance.ativo
        if commit:
            self.instance.save()
        return self.instance


class ConteudoProgramaticoModelForm(forms.ModelForm):
    """
    ModelForm para Criar/Editar uma linha de Conteúdo Programático — 'disciplina'
    resolvida pela URL (dispatch), nunca pelo formulário. CRU — sem Delete, mesmo
    padrão de Disciplina (rastreabilidade do que foi definido para ser ministrado).
    """
    class Meta:
        model = ConteudoProgramatico
        fields = ['ordem', 'descricao', 'observacao']
        widgets = {
            'observacao': forms.Textarea(attrs={'rows': 3, 'style': 'width:100%; box-sizing:border-box;'}),
        }


class ConteudoProgramaticoToggleAtivoForm(forms.ModelForm):
    """Mesmo padrão de DisciplinaToggleAtivoForm, para uma linha de Conteúdo Programático."""
    class Meta:
        model = ConteudoProgramatico
        fields = []

    def save(self, commit=True):
        self.instance.ativo = not self.instance.ativo
        if commit:
            self.instance.save()
        return self.instance


class SubModuloModelForm(forms.ModelForm):
    """Criar/Editar SubModulo (CRU — sem Delete, mesmo padrão de Disciplina). 'ativo' fica de fora, toggle é ação própria."""
    class Meta:
        model = SubModulo
        fields = ['nome', 'sigla']


class SubModuloToggleAtivoForm(forms.ModelForm):
    """Mesmo padrão de DisciplinaToggleAtivoForm."""
    class Meta:
        model = SubModulo
        fields = []

    def save(self, commit=True):
        self.instance.ativo = not self.instance.ativo
        if commit:
            self.instance.save()
        return self.instance


class SubModuloDisciplinaModelForm(forms.ModelForm):
    """
    Vincula uma Disciplina já cadastrada a um SubModulo, com 'ordem'. 'submodulo'
    é passado pela View (nunca pelo formulário) e usado aqui só para validar
    duplicidade com mensagem amigável — o UNIQUE do banco já protege, isso é
    só para o erro aparecer de forma clara (ver docs/34).

    Desvincular (Delete real de SubModuloDisciplina) não afeta rastreabilidade:
    ConteudoProgramatico.disciplina aponta direto para Disciplina, nunca passa
    por este vínculo — decisão confirmada em 05/09/2026, ver docs/34.
    """
    class Meta:
        model = SubModuloDisciplina
        fields = ['disciplina', 'ordem']

    def __init__(self, *args, **kwargs):
        self.submodulo = kwargs.pop('submodulo')
        super().__init__(*args, **kwargs)
        # Só oferece Disciplinas ativas no dropdown — catálogo pequeno hoje
        # (dezenas de itens), dropdown simples é suficiente por enquanto.
        self.fields['disciplina'].queryset = Disciplina.objects.filter(ativo=True).order_by('nome')

    def clean_disciplina(self):
        disciplina = self.cleaned_data['disciplina']
        if SubModuloDisciplina.objects.filter(submodulo=self.submodulo, disciplina=disciplina).exists():
            raise forms.ValidationError("Esta Disciplina já está vinculada a este SubModulo.")
        return disciplina

    def clean_ordem(self):
        ordem = self.cleaned_data['ordem']
        if SubModuloDisciplina.objects.filter(submodulo=self.submodulo, ordem=ordem).exists():
            raise forms.ValidationError("Já existe uma Disciplina nesta posição (ordem) deste SubModulo.")
        return ordem


class ModuloModelForm(forms.ModelForm):
    """Criar/Editar Modulo (CRU — sem Delete, mesmo padrão de Disciplina/SubModulo)."""
    class Meta:
        model = Modulo
        fields = ['nome', 'sigla', 'descricao']


class ModuloToggleAtivoForm(forms.ModelForm):
    """Mesmo padrão de DisciplinaToggleAtivoForm/SubModuloToggleAtivoForm."""
    class Meta:
        model = Modulo
        fields = []

    def save(self, commit=True):
        self.instance.ativo = not self.instance.ativo
        if commit:
            self.instance.save()
        return self.instance


class ModuloSubModuloModelForm(forms.ModelForm):
    """
    Vincula um SubModulo já cadastrado a um Modulo, com 'ordem'. Mesmo padrão de
    SubModuloDisciplinaModelForm — 'modulo' vem da View, validação de duplicidade
    com mensagem amigável, Delete real permitido no vínculo (desvincular não
    afeta rastreabilidade, ver docs/34).
    """
    class Meta:
        model = ModuloSubModulo
        fields = ['submodulo', 'ordem']

    def __init__(self, *args, **kwargs):
        self.modulo = kwargs.pop('modulo')
        super().__init__(*args, **kwargs)
        self.fields['submodulo'].queryset = SubModulo.objects.filter(ativo=True).order_by('nome')

    def clean_submodulo(self):
        submodulo = self.cleaned_data['submodulo']
        if ModuloSubModulo.objects.filter(modulo=self.modulo, submodulo=submodulo).exists():
            raise forms.ValidationError("Este SubModulo já está vinculado a este Modulo.")
        return submodulo

    def clean_ordem(self):
        ordem = self.cleaned_data['ordem']
        if ModuloSubModulo.objects.filter(modulo=self.modulo, ordem=ordem).exists():
            raise forms.ValidationError("Já existe um SubModulo nesta posição (ordem) deste Modulo.")
        return ordem


class OfertaModuloModelForm(forms.ModelForm):
    """
    Criar/Editar OfertaModulo — 'data_fim' e 'ativo' ficam de fora: preenchidos
    só pela ação de Encerrar (EncerrarOfertaModuloForm), nunca aqui.

    Reativar uma Oferta encerrada só é possível pelo Django Admin, de propósito
    (decisão de 05/09/2026) — a tela mostra um aviso, sem botão de Reativar.
    """
    class Meta:
        model = OfertaModulo
        fields = ['modulo', 'ano_letivo', 'data_inicio', 'observacao']
        widgets = {
            'data_inicio': forms.DateInput(attrs={'type': 'date'}),
            'observacao': forms.Textarea(attrs={'rows': 3, 'style': 'width:100%; box-sizing:border-box;'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Só Módulos ativos no dropdown — mas, ao editar uma Oferta já existente,
        # mantém visível o Módulo atual mesmo que ele tenha sido inativado depois.
        queryset = Modulo.objects.filter(ativo=True)
        if self.instance.pk and self.instance.modulo_id:
            queryset = Modulo.objects.filter(Q(ativo=True) | Q(pk=self.instance.modulo_id))
        self.fields['modulo'].queryset = queryset.order_by('nome')


class EncerrarOfertaModuloForm(forms.ModelForm):
    """
    Encerra uma OfertaModulo — exige 'data_fim' (diferente do Model, onde é
    opcional) e marca 'ativo=False'. Mesmo padrão de
    EncerrarHistoricoVinculoFormalForm.
    """
    class Meta:
        model = OfertaModulo
        fields = ['data_fim']
        widgets = {
            'data_fim': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_fim'].required = True

    def save(self, commit=True):
        self.instance.ativo = False
        return super().save(commit=commit)


class TurmaModelForm(forms.ModelForm):
    """
    Criar/Editar Turma — 'oferta_modulo' resolvido pela URL (dispatch), nunca
    pelo formulário. CRU — nunca há Delete de Turma (decisão de 05/09/2026).

    'situacao' NUNCA aparece aqui (corrigido em 08/09/2026) — a transição de
    estado (PLANEJADA→EM_ANDAMENTO→ENCERRADA) só pode acontecer através das
    telas do módulo atribuicao (Finalizar Planejamento / Encerrar Turma), que
    aplicam as regras de negócio (data/Ata obrigatórias, sem retrocesso).
    Deixar 'situacao' editável livre aqui, como estava antes, permitia
    contornar completamente essas regras — bug real encontrado em teste
    manual (ver docs/39).
    """
    class Meta:
        model = Turma
        fields = ['nome', 'sigla', 'periodo', 'observacao']
        widgets = {
            'observacao': forms.Textarea(attrs={'rows': 3, 'style': 'width:100%; box-sizing:border-box;'}),
        }

    def clean_sigla(self):
        # 'oferta_modulo' nunca está em Meta.fields (é resolvido pela URL,
        # não pelo usuário) — por isso o Django NUNCA valida a UniqueConstraint
        # (oferta_modulo, sigla) sozinho, mesmo com a instância já preenchida
        # (a exclusão é por "não é campo do form", não por "valor não setado
        # a tempo"). Sem esta checagem manual, sigla duplicada só falhava na
        # hora de salvar, com IntegrityError cru (tela de debug) em vez de
        # mensagem amigável. Bug real de teste manual, corrigido em 08/09/2026
        # (docs/39).
        sigla = self.cleaned_data['sigla']
        consulta = Turma.objects.filter(oferta_modulo=self.instance.oferta_modulo, sigla=sigla)
        if self.instance.pk:
            consulta = consulta.exclude(pk=self.instance.pk)
        if consulta.exists():
            raise forms.ValidationError("Já existe uma turma cadastrada com esta sigla, nesta Oferta de Módulo.")
        return sigla


class AtaModelForm(forms.ModelForm):
    """Criar/Editar Ata — CRU; Delete só pelo Django Admin (decisão de 05/09/2026)."""
    class Meta:
        model = Ata
        fields = ['numero', 'tipo', 'finalidade', 'data', 'assunto', 'observacao']
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date'}),
            'observacao': forms.Textarea(attrs={'rows': 3, 'style': 'width:100%; box-sizing:border-box;'}),
        }


class AtaPessoaModelForm(forms.ModelForm):
    """
    Vincula um Discente ativo a uma Ata. 'ata' vem da View (dispatch), nunca do
    formulário. Dropdown mostra só Pessoas com AtribuicaoFuncao de Discente
    ATIVA (matriculado agora, não ex-aluno já encerrado) — decisão de
    05/09/2026, ver docs/35.

    EXCEÇÃO PROVISÓRIA (ver AtaPessoa.__doc__ em models.py): este vínculo migra
    para o módulo Atribuição quando ele existir.
    """
    class Meta:
        model = AtaPessoa
        fields = ['pessoa']

    def __init__(self, *args, **kwargs):
        self.ata = kwargs.pop('ata')
        super().__init__(*args, **kwargs)
        self.fields['pessoa'].queryset = Pessoa.objects.filter(
            atribuicoes__dados_discente__isnull=False,
            atribuicoes__ativo=True,
        ).distinct().order_by('nome_completo')

    def clean_pessoa(self):
        pessoa = self.cleaned_data['pessoa']
        if AtaPessoa.objects.filter(ata=self.ata, pessoa=pessoa).exists():
            raise forms.ValidationError("Esta Pessoa já está vinculada a esta Ata.")
        return pessoa


# Formsets
FormacaoDocenteFormSet = forms.formset_factory(FormacaoDocenteForm, extra=1)
ExperienciaProfissionalFormSet = forms.formset_factory(ExperienciaProfissionalForm, extra=1)
HistoricoVinculoFormalFormSet = forms.formset_factory(HistoricoVinculoFormalForm, extra=1)
PendenciaCadastroFormSet = forms.formset_factory(PendenciaCadastroForm, extra=1)

from django import forms
# IMPORTAÇÃO CORRETA: Traz os dois modelos do aplicativo onde eles realmente existem!
from atribuicao.models import ContratoFinanceiro, MedicaoContrato

class ContratoFinanceiroModelForm(forms.ModelForm):
    """
    SRP: Validação técnica e estrutural para inserção/edição de 
    contratos públicos no ecossistema escolar.
    """
    class Meta:
        model = ContratoFinanceiro
        fields = [
            'numero_processo', 'numero_contrato', 'tipo', 'instrutor',
            'credor_razao_social', 'cnpj_cpf_credor', 'valor_total_empenhado',
            'valor_hora_aula', 'data_assinatura', 'data_vigencia_inicio',
            'data_vigencia_fim', 'status', 'objeto_contrato'
        ]
        widgets = {
            'numero_processo': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_contrato': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'instrutor': forms.Select(attrs={'class': 'form-select'}),
            'credor_razao_social': forms.TextInput(attrs={'class': 'form-control'}),
            'cnpj_cpf_credor': forms.TextInput(attrs={'class': 'form-control'}),
            'valor_total_empenhado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'valor_hora_aula': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'data_assinatura': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_vigencia_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_vigencia_fim': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'objeto_contrato': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        inicio = cleaned_data.get('data_vigencia_inicio')
        fim = cleaned_data.get('data_vigencia_fim')

        if inicio and fim and fim < inicio:
            raise forms.ValidationError("A data de fim da vigência não pode ser anterior à data de início.")
        
        return cleaned_data

class MedicaoContratoForm(forms.ModelForm):
    class Meta:
        model = MedicaoContrato
        fields = ['contrato', 'numero_parcela', 'valor_medido', 'status']
        widgets = {
            'contrato': forms.Select(attrs={'style': 'width: 100%; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.9rem;'}),
            'numero_parcela': forms.NumberInput(attrs={'style': 'width: 100%; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.9rem;', 'placeholder': 'Ex: 1'}),
            'valor_medido': forms.NumberInput(attrs={'style': 'width: 100%; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.9rem;', 'placeholder': 'Ex: 4500.00', 'step': '0.01'}),
            'status': forms.Select(attrs={'style': 'width: 100%; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.9rem;'}),
        }


from django import forms
from atribuicao.models import Atribuicao
from cadastros.models import AtribuicaoFuncao

class AtribuicaoInstrutorForm(forms.ModelForm):
    class Meta:
        model = Atribuicao
        fields = ['instrutor', 'disciplina', 'turma']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. ESTILIZAÇÃO DAS SETAS
        self.fields['instrutor'].widget.attrs.update({'class': 'form-control select2'})
        self.fields['disciplina'].widget.attrs.update({'class': 'form-control'})
        self.fields['turma'].widget.attrs.update({'class': 'form-control'})

        # 2. FILTRAGEM AUTOMÁTICA (Remove Alunos e Discentes da lista)
        # Como vimos na imagem que o seu sistema usa as palavras "Aluno" e "discente",
        # filtramos o banco para travar e não trazer essas funções na seta de professores.
        self.fields['instrutor'].queryset = AtribuicaoFuncao.objects.select_related('pessoa').exclude(
            forms.models.Q(cargo__icontains='aluno') | 
            forms.models.Q(cargo__icontains='discente')
        ).order_by('pessoa__nome_completo')


