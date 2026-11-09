"""
atribuicao/forms.py
"""

from django import forms

from cadastros.models import Pessoa, Ata, FinalidadeAta, CategoriaModulo, Turma, SituacaoTurma
from cadastros.services import ObterOuCriarAtribuicaoDiscenteService
from .models import MatriculaTurma, StatusMatriculaTurma, MotivoSaida
from .services import atribuicoes_elegiveis_para_turma_regular


class AdicionarMatriculaTurmaForm(forms.ModelForm):
    """
    Popup "+ Adicionar Aluno" (docs/37, seção 4.1). Nenhum campo do próprio
    Model no formulário (fields=[]) — 'pessoa' e 'codigo_matricula_anac' são
    resolvidos aqui, e a AtribuicaoFuncao correspondente é obtida/criada via
    ObterOuCriarAtribuicaoDiscenteService (cadastros) dentro de save().

    Dropdown de Pessoa depende do tipo da Turma: Extracurricular aceita
    qualquer Pessoa; Turma regular só aceita Discente ATIVO "Aguardando
    Atribuição/Turma" (ver atribuicoes_elegiveis_para_turma_regular).
    """
    pessoa = forms.ModelChoiceField(queryset=Pessoa.objects.none(), label="Aluno")
    codigo_matricula_anac = forms.CharField(max_length=20, required=False, label="Código de Matrícula ANAC")

    class Meta:
        model = MatriculaTurma
        fields = []

    def __init__(self, *args, **kwargs):
        self.turma = kwargs.pop('turma')
        super().__init__(*args, **kwargs)

        if self.turma.oferta_modulo.modulo.categoria == CategoriaModulo.EXTRACURRICULAR:
            self.fields['pessoa'].queryset = Pessoa.objects.all().order_by('nome_completo')
        else:
            elegiveis = atribuicoes_elegiveis_para_turma_regular()
            self.fields['pessoa'].queryset = Pessoa.objects.filter(
                id__in=elegiveis.values_list('pessoa_id', flat=True)
            ).order_by('nome_completo')

    def clean_pessoa(self):
        pessoa = self.cleaned_data['pessoa']
        if MatriculaTurma.objects.filter(turma=self.turma, atribuicao_funcao__pessoa=pessoa).exists():
            raise forms.ValidationError("Esta Pessoa já está matriculada nesta Turma.")
        return pessoa

    def clean_codigo_matricula_anac(self):
        # DadosDiscente.codigo_matricula_anac é unique=True, mas como esse
        # campo pertence a outro Model (não é campo de MatriculaTurma), o
        # Django nunca valida essa duplicidade sozinho — sem essa checagem,
        # um valor repetido só falhava na hora de salvar, com IntegrityError
        # cru (tela de debug) em vez de mensagem amigável. Bug real de teste
        # manual, corrigido em 08/09/2026 (docs/39).
        from cadastros.models import DadosDiscente

        canac = self.cleaned_data.get('codigo_matricula_anac')
        if canac and DadosDiscente.objects.filter(codigo_matricula_anac=canac).exists():
            raise forms.ValidationError(f"Código de Matrícula ANAC '{canac}' já está em uso.")
        return canac

    def save(self, commit=True):
        from django.db.models import Max
        from django.utils import timezone

        pessoa = self.cleaned_data['pessoa']
        canac = self.cleaned_data.get('codigo_matricula_anac')

        atribuicao = ObterOuCriarAtribuicaoDiscenteService().executar(pessoa, timezone.now().date())
        if canac and not atribuicao.dados_discente.codigo_matricula_anac:
            atribuicao.dados_discente.codigo_matricula_anac = canac
            atribuicao.dados_discente.save()

        self.instance.atribuicao_funcao = atribuicao
        self.instance.turma = self.turma

        # Turma já EM_ANDAMENTO (aluno relocado entrando, ou Extracurricular novo):
        # numero_na_turma = MAX+1 desta Turma, e ganha data_inicio na hora. Enquanto
        # PLANEJADA, isso fica para "Finalizar Planejamento" (docs/37, seção 4.3).
        if self.turma.situacao != SituacaoTurma.PLANEJADA:
            max_atual = MatriculaTurma.objects.filter(turma=self.turma).aggregate(
                Max('numero_na_turma')
            )['numero_na_turma__max'] or 0
            self.instance.numero_na_turma = max_atual + 1
            self.instance.data_inicio = timezone.now().date()

        return super().save(commit=commit)


class EditarMatriculaTurmaForm(forms.ModelForm):
    """
    Popup "Editar/CRU" enquanto a Turma está PLANEJADA (docs/37, seção 4.1) —
    só corrige o Código de Matrícula ANAC (que mora em DadosDiscente, não em
    MatriculaTurma). A edição de 'status' (Em Andamento) é um Form separado,
    ainda não implementado nesta etapa.
    """
    codigo_matricula_anac = forms.CharField(max_length=20, required=False, label="Código de Matrícula ANAC")

    class Meta:
        model = MatriculaTurma
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['codigo_matricula_anac'].initial = (
            self.instance.atribuicao_funcao.dados_discente.codigo_matricula_anac
        )

    def save(self, commit=True):
        dados_discente = self.instance.atribuicao_funcao.dados_discente
        dados_discente.codigo_matricula_anac = self.cleaned_data.get('codigo_matricula_anac') or None
        dados_discente.save()
        return self.instance


class FinalizarPlanejamentoForm(forms.Form):
    """Popup do botão "Finalizar Planejamento" (docs/37, seção 4.2)."""
    data_inicio = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}), label="Data de Início"
    )
    ata_inicio = forms.ModelChoiceField(
        queryset=Ata.objects.filter(finalidade=FinalidadeAta.INICIO_VINCULO).order_by('-data'),
        label="Ata de Início de Vínculo",
        help_text="A Ata precisa já existir — cadastre em /cadastros/atas/ antes, se necessário.",
    )



class EditarStatusMatriculaForm(forms.Form):
    """
    Popup "Editar/CRU" enquanto a Turma está EM_ANDAMENTO (docs/37, seção 4.3)
    — só chamado quando matricula.status ainda é CURSANDO. Campos exigidos
    variam por 'status' escolhido, validados em clean() (sem JS condicional
    nesta etapa — todos os campos aparecem sempre, com texto explicando
    quando cada um se aplica).
    """
    status = forms.ChoiceField(
        choices=[
            (StatusMatriculaTurma.RELOCADO, 'Relocado'),
            (StatusMatriculaTurma.REPROVADO, 'Reprovado'),
            (StatusMatriculaTurma.TRANSFERIDO, 'Transferido'),
            (StatusMatriculaTurma.MATRICULA_EXCLUIDA, 'Matrícula Excluída'),
        ],
        label="Novo Status",
    )
    turma_destino = forms.ModelChoiceField(
        queryset=Turma.objects.none(), required=False,
        label="Turma de destino", help_text="Obrigatório só para Relocado.",
    )
    motivo_saida = forms.ChoiceField(
        choices=[('', '---------')] + list(MotivoSaida.choices), required=False,
        label="Motivo da saída", help_text="Obrigatório só para Transferido.",
    )
    data_fim = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}), required=False,
        label="Data de Fim", help_text="Obrigatório para Reprovado/Transferido/Matrícula Excluída.",
    )
    ata_encerramento = forms.ModelChoiceField(
        queryset=Ata.objects.filter(finalidade=FinalidadeAta.TERMINO_VINCULO).order_by('-data'),
        required=False, label="Ata de Término de Vínculo",
        help_text="Obrigatório para Reprovado/Transferido/Matrícula Excluída — a Ata precisa já existir.",
    )

    def __init__(self, *args, **kwargs):
        self.matricula = kwargs.pop('matricula')
        super().__init__(*args, **kwargs)
        self.fields['turma_destino'].queryset = Turma.objects.filter(
            situacao=SituacaoTurma.EM_ANDAMENTO
        ).exclude(pk=self.matricula.turma_id).order_by('nome')

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')

        if status == StatusMatriculaTurma.RELOCADO:
            if not cleaned_data.get('turma_destino'):
                self.add_error('turma_destino', "Obrigatório para Relocado.")
        elif status == StatusMatriculaTurma.TRANSFERIDO:
            if not cleaned_data.get('motivo_saida'):
                self.add_error('motivo_saida', "Obrigatório para Transferido.")
            if not cleaned_data.get('data_fim'):
                self.add_error('data_fim', "Obrigatório.")
            if not cleaned_data.get('ata_encerramento'):
                self.add_error('ata_encerramento', "Obrigatório.")
        elif status in (StatusMatriculaTurma.REPROVADO, StatusMatriculaTurma.MATRICULA_EXCLUIDA):
            if not cleaned_data.get('data_fim'):
                self.add_error('data_fim', "Obrigatório.")
            if not cleaned_data.get('ata_encerramento'):
                self.add_error('ata_encerramento', "Obrigatório.")

        return cleaned_data


class RevisarAprovacaoForm(forms.Form):
    """
    1º clique de "Encerrar Turma" (docs/37, seção 8-A, fechada em 07/09/2026)
    — um campo BooleanField por aluno ainda CURSANDO, marcado por padrão
    (self.matriculas_cursando guarda a lista, na mesma ordem usada para criar
    os campos — usado pelo template via form.linhas para parear cada
    matrícula com seu checkbox correspondente).
    """

    def __init__(self, *args, **kwargs):
        self.turma = kwargs.pop('turma')
        super().__init__(*args, **kwargs)
        self.matriculas_cursando = list(
            MatriculaTurma.objects.filter(turma=self.turma, status=StatusMatriculaTurma.CURSANDO)
            .select_related('atribuicao_funcao__pessoa')
            .order_by('numero_na_turma')
        )
        for matricula in self.matriculas_cursando:
            self.fields[f'aprovar_{matricula.pk}'] = forms.BooleanField(
                required=False, initial=True, label=matricula.atribuicao_funcao.pessoa.nome_completo,
            )

    def linhas(self):
        for matricula in self.matriculas_cursando:
            yield matricula, self[f'aprovar_{matricula.pk}']

    def matriculas_aprovadas_ids(self):
        return [m.pk for m in self.matriculas_cursando if self.cleaned_data.get(f'aprovar_{m.pk}')]


class EncerrarTurmaForm(forms.Form):
    """
    2º clique de "Encerrar Turma" (docs/37, seção 4.4). 'ata_encerramento'
    fica escondida para Turma de Módulo Básico (nunca fecha vínculo) — para
    Especializado/Extracurricular, é exigida (mesmo que, no caso do
    Extracurricular, acabe não sendo usada para quem está acumulando com uma
    Turma regular — simplificação aceita por ora, ver docs/37 seção 7).
    """
    data_encerramento = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}), label="Data de Encerramento"
    )
    ata_encerramento = forms.ModelChoiceField(
        queryset=Ata.objects.filter(finalidade=FinalidadeAta.TERMINO_VINCULO).order_by('-data'),
        required=False, label="Ata de Término de Vínculo",
    )

    def __init__(self, *args, **kwargs):
        self.turma = kwargs.pop('turma')
        super().__init__(*args, **kwargs)
        if self.turma.oferta_modulo.modulo.categoria == CategoriaModulo.BASICO:
            self.fields['ata_encerramento'].widget = forms.HiddenInput()
        else:
            self.fields['ata_encerramento'].required = True

# ==========================================================
# NOVO FORMULÁRIO: ATRIBUIÇÃO DE DISCIPLINAS (COORDENAÇÃO)
# ==========================================================
from atribuicao.models import Atribuicao
from cadastros.models import AtribuicaoFuncao, Disciplina, Turma

class CriarAtribuicaoForm(forms.ModelForm):
    """
    Formulário para a aba Coordenação (Nova Atribuição de Disciplina).
    Carrega dinamicamente os dados cadastrados na Secretaria.
    """
    instrutor = forms.ModelChoiceField(
        queryset=AtribuicaoFuncao.objects.filter(situacao='ATIVO'), # Filtra apenas profissionais ativos
        label="Instrutor / Professor",
        empty_label="Selecione um instrutor..."
    )
    disciplina = forms.ModelChoiceField(
        queryset=Disciplina.objects.all().order_by('nome'),
        label="Disciplina",
        empty_label="Selecione a disciplina..."
    )
    turma = forms.ModelChoiceField(
        queryset=Turma.objects.filter(status='PLANEJADA').order_by('nome'), # Traz as turmas planejadas/ativas
        label="Turma",
        empty_label="Selecione a turma..."
    )

    class Meta:
        model = Atribuicao
        fields = ['instrutor', 'disciplina', 'turma']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Injeta classes CSS para garantir que o Django renderize com o estilo do seu layout Bootstrap/CSS
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-select'})

from django import forms
from .models import Atribuicao
from cadastros.models import AtribuicaoFuncao  # Ajuste o import se o nome do model no app cadastros for diferente


class AtribuicaoInstrutorForm(forms.ModelForm):
    class Meta:
        model = Atribuicao
        fields = ['instrutor', 'disciplina', 'turma']
        labels = {
            'instrutor': 'Instrutor / Professor',
            'disciplina': 'Disciplina',
            'turma': 'Turma',
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. ESTILIZAÇÃO PROFISSIONAL: Aplica classes do Bootstrap uniformemente
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})
            
        # Adiciona a classe select2 especificamente no instrutor para buscas rápidas
        self.fields['instrutor'].widget.attrs.update({'class': 'form-control'})


        # 2. BLINDAGEM DE ARQUITETURA: Filtra apenas perfis com situação ATIVA e que NÃO sejam discentes
        # Import local seguro para evitar loops de carregamento
        from cadastros.models import SituacaoAtribuicao
        from django.db.models import Q

        self.fields['instrutor'].queryset = self.fields['instrutor'].queryset.select_related('pessoa', 'funcao').filter(
            situacao=SituacaoAtribuicao.ATIVO
        ).exclude(
            Q(funcao__nome__icontains='aluno') | 
            Q(funcao__nome__icontains='discente')
        ).order_by('pessoa__nome_completo')
        
        # 3. FILTRO DE TURMAS OPERACIONAIS: Impede vincular instrutores a turmas já encerradas
        from cadastros.models import SituacaoTurma
        self.fields['turma'].queryset = self.fields['turma'].queryset.exclude(
            status=SituacaoTurma.ENCERRADA
        ).order_by('ano_letivo', 'nome')


from django import forms
from django.core.exceptions import ValidationError
from .models import HorarioAula

class HorarioAulaForm(forms.ModelForm):
    class Meta:
        model = HorarioAula
        fields = ['atribuicao', 'dia_semana', 'horario_inicio', 'horario_fim']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Estiliza e otimiza a seta de vínculos
        self.fields['atribuicao'].widget.attrs.update({'class': 'form-control select2'})
        self.fields['atribuicao'].queryset = self.fields['atribuicao'].queryset.select_related(
            'instrutor__pessoa', 'disciplina', 'turma'
        )
        # Estiliza os demais campos
        self.fields['dia_semana'].widget.attrs.update({'class': 'form-control'})
        self.fields['horario_inicio'].widget.attrs.update({'class': 'form-control', 'type': 'time'})
        self.fields['horario_fim'].widget.attrs.update({'class': 'form-control', 'type': 'time'})

    def clean(self):
        cleaned_data = super().clean()
        atribuicao = cleaned_data.get('atribuicao')
        dia_semana = cleaned_data.get('dia_semana')
        horario_inicio = cleaned_data.get('horario_inicio')
        horario_fim = cleaned_data.get('horario_fim')

        # Se algum dado obrigatório estiver faltando, deixa os validadores padrão do Django agirem
        if not (atribuicao and dia_semana and horario_inicio and horario_fim):
            return cleaned_data

        # VALIDAÇÃO 1: Impede inversão de lógica temporal
        if horario_inicio >= horario_fim:
            raise ValidationError({
                'horario_inicio': "O horário de início deve ser menor do que o horário de término da aula."
            })

        # VALIDAÇÃO 2: Algoritmo Antichoque de Horário do Instrutor
        # Busca se já existe QUALQUEER horário agendado para o MESMO instrutor, no MESMO dia, 
        # onde as faixas de horários se sobreponham (concorrência de tempo)
        instrutor_id = atribuicao.instrutor_id
        
        conflitos_instrutor = HorarioAula.objects.filter(
            atribuicao__instrutor_id=instrutor_id,
            dia_semana=dia_semana,
            horario_inicio__lt=horario_fim,   # Início do existente acontece antes do fim do novo
            horario_fim__gt=horario_inicio    # Fim do existente acontece depois do início do novo
        )

        # Se estamos editando um horário existente, exclui ele próprio da checagem de conflitos
        if self.instance and self.instance.pk:
            conflitos_instrutor = conflitos_instrutor.exclude(pk=self.instance.pk)

        if conflitos_instrutor.exists():
            conflito = conflitos_instrutor.first()
            raise ValidationError(
                f"Choque de Agenda! O professor {atribuicao.instrutor.pessoa.nome_completo} "
                f"já possui uma aula vinculada neste mesmo dia ({dia_semana}) entre às "
                f"{conflito.horario_inicio.strftime('%H:%M')} e {conflito.horario_fim.strftime('%H:%M')} "
                f"na turma {conflito.atribuicao.turma.nome}."
            )

        # VALIDAÇÃO 3 (Opcional - Antichoque de Sala/Turma):
        # Se você também quiser impedir que duas matérias diferentes usem a mesma TURMA no mesmo horário:
        conflitos_turma = HorarioAula.objects.filter(
            atribuicao__turma_id=atribuicao.turma_id,
            dia_semana=dia_semana,
            horario_inicio__lt=horario_fim,
            horario_fim__gt=horario_inicio
        )
        if self.instance and self.instance.pk:
            conflitos_turma = conflitos_turma.exclude(pk=self.instance.pk)

        if conflitos_turma.exists():
            conflito_t = conflitos_turma.first()
            raise ValidationError(
                f"Conflito de Sala! A turma {atribuicao.turma.nome} já possui a disciplina "
                f"{conflito_t.atribuicao.disciplina.nome} alocada neste mesmo horário."
            )

        return cleaned_data

from django import forms
from .models import RegistroInstrucao

class RegistroInstrucaoForm(forms.ModelForm):
    class Meta:
        model = RegistroInstrucao
        # Adicione aqui os campos exatos do seu modelo que estão no formulário
        fields = ['data_instrucao', 'carga_horaria', 'tipo_instrucao', 'conteudo_programatico']

from django import forms
from .models import ContratoFinanceiro

class ContratoFinanceiroForm(forms.ModelForm):
    class Meta:
        model = ContratoFinanceiro
        # Liberamos estes dois campos para preenchimento no formulário:
        fields = ['valor_total_empenhado', 'status']

from django import forms
from .models import ContratoFinanceiro

class ContratoFinanceiroForm(forms.ModelForm):
    class Meta:
        model = ContratoFinanceiro
        fields = ['valor_total_empenhado', 'status']

from .models import MedicaoContrato

class MedicaoContratoForm(forms.ModelForm):
    class Meta:
        model = MedicaoContrato
        fields = ['contrato', 'numero_parcela', 'valor_medido', 'status']
