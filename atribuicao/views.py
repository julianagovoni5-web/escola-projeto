from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView, ListView, TemplateView
from django.db.models import Sum, Count, Q

from cadastros.models import Turma, SituacaoTurma
from cadastros.views import ModalCrudMixin

from .forms import (
    AdicionarMatriculaTurmaForm, EditarMatriculaTurmaForm, FinalizarPlanejamentoForm,
    EditarStatusMatriculaForm, AtribuicaoInstrutorForm, HorarioAulaForm, RegistroInstrucaoForm
)
from .models import MatriculaTurma, StatusMatriculaTurma, RegistroInstrucao, HorarioAula, Atribuicao, ContratoFinanceiro

# =========================================================================
# MÓDULO DE ATRIBUIÇÃO E MATRÍCULAS DE ALUNOS
# =========================================================================

class GerenciarTurmaView(DetailView):
    """Tela principal do módulo Atribuição — composição de alunos de uma Turma."""
    model = Turma
    template_name = 'atribuicao/gerenciar_turma.html'
    context_object_name = 'turma'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        matriculas = self.object.matriculas.select_related('atribuicao_funcao__pessoa')
        if self.object.situacao == SituacaoTurma.PLANEJADA:
            matriculas = matriculas.order_by('atribuicao_funcao__pessoa__nome_completo')
        else:
            matriculas = matriculas.order_by('numero_na_turma')
        context['matriculas'] = matriculas
        context['ha_cursando'] = self.object.matriculas.filter(status=StatusMatriculaTurma.CURSANDO).exists()
        
        # Histórico de professores vinculados nesta turma específica
        context['atribuicoes_professores'] = Atribuicao.objects.filter(
            turma=self.object
        ).select_related('instrutor__pessoa', 'disciplina')
        return context


class AdicionarMatriculaTurmaView(ModalCrudMixin, CreateView):
    model = MatriculaTurma
    form_class = AdicionarMatriculaTurmaForm
    template_name = 'atribuicao/form_matricula.html'
    template_fragmento = 'atribuicao/_form_matricula_fragment.html'

    def dispatch(self, request, *args, **kwargs):
        self.turma = get_object_or_404(Turma, pk=kwargs['pk'])
        if self.turma.situacao == SituacaoTurma.ENCERRADA:
            raise Http404("Não é possível adicionar aluno a uma Turma já Encerrada.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['turma'] = self.turma
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['turma'] = self.turma
        return context

    def get_success_url(self):
        return reverse('gerenciar-turma', kwargs={'pk': self.turma.pk})


class EditarMatriculaTurmaView(ModalCrudMixin, UpdateView):
    model = MatriculaTurma
    form_class = EditarMatriculaTurmaForm
    template_name = 'atribuicao/form_matricula.html'
    template_fragmento = 'atribuicao/_form_matricula_fragment.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['turma'] = self.object.turma
        context['editando'] = True
        return context

    def get_success_url(self):
        return reverse('gerenciar-turma', kwargs={'pk': self.object.turma_id})


class ExcluirMatriculaTurmaView(ModalCrudMixin, DeleteView):
    """Delete físico — só permitido enquanto a Turma está PLANEJADA."""
    model = MatriculaTurma
    template_name = 'cadastros/confirmar_exclusao.html'
    template_fragmento = 'cadastros/_confirmar_exclusao_fragment.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.turma.situacao != SituacaoTurma.PLANEJADA:
            raise Http404("Só é possível excluir uma matrícula enquanto a Turma está Planejada.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['url_voltar'] = reverse('gerenciar-turma', kwargs={'pk': self.object.turma_id})
        return context

    def get_success_url(self):
        return reverse('gerenciar-turma', kwargs={'pk': self.object.turma_id})


class FinalizarPlanejamentoView(View):
    def _template(self, request):
        return 'atribuicao/_form_finalizar_planejamento_fragment.html' if request.GET.get('parcial') == '1' \
            else 'atribuicao/form_finalizar_planejamento.html'

    def get(self, request, pk):
        turma = get_object_or_404(Turma, pk=pk)
        form = FinalizarPlanejamentoForm()
        return render(request, self._template(request), {'form': form, 'turma': turma})


class EditarStatusMatriculaView(View):
    def _template(self, request):
        return 'atribuicao/_form_status_matricula_fragment.html' if request.GET.get('parcial') == '1' \
            else 'atribuicao/form_status_matricula.html'

    def _matricula_ou_404(self, pk):
        matricula = get_object_or_404(MatriculaTurma, pk=pk)
        if matricula.status != StatusMatriculaTurma.CURSANDO:
            raise Http404("Só é possível alterar o status de uma matrícula ainda Cursando.")
        return matricula

    def get(self, request, pk):
        matricula = self._matricula_ou_404(pk)
        form = EditarStatusMatriculaForm(matricula=matricula)
        return render(request, self._template(request), {'form': form, 'matricula': matricula})


class RevisarAprovacaoView(View):
    def get(self, request, pk):
        return render(request, 'atribuicao/form_revisar_aprovacao.html')


class EncerrarTurmaView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'atribuicao/encerrar_turma.html')


# =========================================================================
# DIÁRIO DE CLASSE, HORÁRIOS E RELATÓRIOS GLOBAIS
# =========================================================================

from django.shortcuts import render, redirect
from .models import RegistroInstrucao
from .forms import RegistroInstrucaoForm  

def registro_instrucao_view(request):
    """Visualização e gravação manual do registro de conteúdos diários."""
    
    if request.method == "POST":
        # 1. Pega os valores exatamente como estão descritos no 'name' do seu HTML:
        data_instrucao = request.POST.get('data_instrucao')
        carga_horaria = request.POST.get('carga_horaria')
        tipo_recebido = request.POST.get('tipo')      # Pega do name="tipo"
        conteudo_recebido = request.POST.get('conteudo')  # Pega do name="conteudo"
        
        # 2. IMPORTANTE: Precisamos vincular a uma atribuição ativa.
        # Como teste para funcionar imediatamente, vamos pegar a primeira atribuição existente.
        # (Depois você pode mudar para pegar a atribuição vinda da URL ou da sessão)
        from .models import Atribuicao # Ajuste o import se o modelo Atribuicao estiver em outro arquivo
        atribuicao_atual = Atribuicao.objects.first() 
        
        if atribuicao_atual and data_instrucao and carga_horaria:
            # 3. Cria e grava diretamente no banco de dados usando os campos do seu Model
            RegistroInstrucao.objects.create(
                atribuicao=atribuicao_atual,
                data_instrucao=data_instrucao,
                carga_horaria=carga_horaria,
                tipo_instrucao=tipo_recebido,       # Atribui ao campo do model
                conteudo_programatico=conteudo_recebido # Atribui ao campo do model
            )
            return redirect(request.path) # Recarrega a página limpa e salva
        else:
            print("Erro: Faltam dados obrigatórios ou nenhuma Atribuição foi encontrada no sistema.")

    # Busca padrão para listar na tabela do lado direito (GET)
    registros = RegistroInstrucao.objects.select_related(
        'atribuicao__instrutor__pessoa', 'atribuicao__disciplina', 'atribuicao__turma'
    ).order_by('-data_instrucao')
    
    return render(request, 'atribuicao/registro_instrucao.html', {'registros': registros})

def horarios_view(request):
    """Gerencia a alocação de horários oficiais acoplados na grade semanal."""
    if request.method == 'POST':
        atribuicao_id = request.POST.get('atribuicao')
        dia_semana = request.POST.get('dia_semana')
        horario_inicio = request.POST.get('horario_inicio')
        horario_fim = request.POST.get('horario_fim')
        if atribuicao_id and dia_semana and horario_inicio and horario_fim:
            HorarioAula.objects.create(
                atribuicao_id=atribuicao_id, dia_semana=dia_semana,
                horario_inicio=horario_inicio, horario_fim=horario_fim
            )
            return redirect('horarios')

    atribuigoes = Atribuicao.objects.select_related('instrutor__pessoa', 'disciplina', 'turma').order_by('disciplina__nome')
    dias_semana = [('SEG', 'Segunda-feira'), ('TER', 'Terça-feira'), ('QUA', 'Quarta-feira'), ('QUI', 'Quinta-feira'), ('SEX', 'Sexta-feira')]
    quadro_geral = HorarioAula.objects.select_related('atribuicao__instrutor__pessoa', 'atribuicao__disciplina', 'atribuicao__turma').order_by('dia_semana', 'horario_inicio')
    
    return render(request, 'atribuicao/horarios.html', {
        'atribuigoes': atribuigoes, 'dias_semana': dias_semana, 'quadro_geral': quadro_geral
    })


def relatorios_view(request):
    """Calcula os indicadores gerenciais em tempo real para os cards."""
    horas_query = RegistroInstrucao.objects.aggregate(total=Sum('carga_horaria'))
    total_horas = int(horas_query['total'] or 0)
    matriculas_ativas = MatriculaTurma.objects.filter(status=StatusMatriculaTurma.CURSANDO).count()
    total_atribuicoes = Atribuicao.objects.count()

    return render(request, 'atribuicao/relatorios.html', {
        'total_horas': total_horas, 
        'matriculas_ativas': matriculas_ativas, 
        'total_atribuicoes': total_atribuicoes
    })


def dashboard_gestao_view(request):
    """Visão geral operacional do Painel de Controle com alertas automáticos de status."""
    total_alunos = MatriculaTurma.objects.filter(status=StatusMatriculaTurma.CURSANDO).count()
    turmas_andamento = Turma.objects.filter(status__icontains='andamento').count() or Turma.objects.filter(status__icontains='cursando').count()
    
    alerta_planejamento = Turma.objects.filter(status__icontains='planej').exists()
    alerta_contratos = True 
    
    total_alertas = sum([1 for x in [alerta_planejamento, alerta_contratos] if x])

    return render(request, 'atribuicao/dashboard.html', {
        'total_alunos': total_alunos, 
        'turmas_andamento': turmas_andamento, 
        'total_alertas': total_alertas,
        'alerta_planejamento': alerta_planejamento, 
        'alerta_contratos': alerta_contratos,
    })


from django.shortcuts import render, redirect
from django.db.models import Sum
from .models import ContratoFinanceiro
from .forms import ContratoFinanceiroForm  # Certifique-se de que o ContratoFinanceiroForm existe no seu forms.py

def contratos_gestao_view(request):
    """Visualização, cálculo dinâmico e inserção de contratos financeiros."""
    
    # 1. SE O USUÁRIO CLICOU EM GRAVAR (POST)
    if request.method == "POST":
        form = ContratoFinanceiroForm(request.POST)
        if form.is_valid():
            form.save()  # Salva o novo contrato digitado no banco de dados!
            return redirect(request.path)  # Recarrega a página limpa com os dados salvos
        else:
            print("ERROS DE VALIDAÇÃO DO CONTRATO:", form.errors)
    else:
        form = ContratoFinanceiroForm()

    # 2. CÁLCULO DOS VALORES REAIS DO BANCO (Substituindo o valor fixo de 150.000,00)
    soma_real = ContratoFinanceiro.objects.filter(status='VIGENTE').aggregate(total=Sum('valor_total_empenhado'))['total'] or 0
    total_contratos_vigentes = ContratoFinanceiro.objects.filter(status='VIGENTE').count()
    
    # 3. BUSCA A LISTA COMPLETA DE CONTRATOS PARA EXIBIR NA TABELA
    contratos = ContratoFinanceiro.objects.all().order_by('-id')

    # 4. MONTA O CONTEXTO DINÂMICO PARA O HTML
    contexto_financeiro = {
        'form': form,
        'total_contratos': total_contratos_vigentes,
        'total_empenhado': soma_real,
        'contratos': contratos
    }
    
    return render(request, 'atribuicao/contratos.html', contexto_financeiro)


# =========================================================================
# MÓDULO DE COORDENAÇÃO: ATRIBUIÇÃO DE DISCIPLINAS
# =========================================================================

class AtribuicaoDisciplinaView(TemplateView):
    """Gerencia a amarração oficial de instrutores às disciplinas com histórico integrado."""
    template_name = 'atribuicao/atribuicao.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = AtribuicaoInstrutorForm()
        context['historico'] = Atribuicao.objects.select_related('instrutor__pessoa', 'disciplina', 'turma').order_by('-id')
        return context

    def post(self, request, *args, **kwargs):
        form = AtribuicaoInstrutorForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('atribuicao-disciplina')
        context = self.get_context_data(**kwargs)
        context['form'] = form
        return self.render_to_response(context)



# =========================================================================
# MÓDULO DE QUALIDADE — DIRECIONADO PARA A PASTA NUCLEO (CORRIGIDO)
# =========================================================================

class TreinamentoListView(ListView):
    """Rastreia de forma macro as execuções diárias de carga horária para auditoria da qualidade."""
    model = RegistroInstrucao
    # CORREÇÃO: Aponta para a pasta nucleo e arquivo correto
    template_name = 'nucleo/treinamento.html'
    context_object_name = 'registros'

    def get_queryset(self):
        return RegistroInstrucao.objects.select_related(
            'atribuicao__instrutor__pessoa', 'atribuicao__disciplina', 'atribuicao__turma'
        ).order_by('-data_instrucao')


class AuditoriaInternaListView(ListView):
    """Histórico analítico de segurança de movimentações de atas de início e encerramento."""
    model = MatriculaTurma
    # CORREÇÃO: Aponta para a pasta nucleo e nome exato do arquivo: auditoria_interna.html
    template_name = 'atribuicao/auditoria.html'
    context_object_name = 'movimentacoes'

    def get_queryset(self):
        return MatriculaTurma.objects.select_related(
            'atribuicao_funcao__pessoa', 'turma', 'ata_inicio', 'ata_encerramento'
        ).order_by('-id')

from django.views import View
from django.shortcuts import render, redirect
from django.db.models import Sum
from django.utils import timezone

from cadastros.models import Turma  # <--- Turma vem do app cadastros!
# ADICIONADO MedicaoContrato NA IMPORTAÇÃO ABAIXO:
from .models import MatriculaTurma, StatusMatriculaTurma, ContratoFinanceiro, MedicaoContrato  
from .forms import ContratoFinanceiroForm # Certifique-se de importar o formulário correspondente


class IndicadoresQualidadeView(View):
    """Métricas institucionais consolidadas com inserção direta de contratos financeiros."""

    def get_context_data(self, request, ano_selecionado):
        """Função auxiliar para agrupar os cálculos matemáticos da tela."""
        ano_atual = timezone.now().year
        
        # Lista retroativa garantida de anos
        anos_validos = [ano_atual - i for i in range(6)]
        anos_banco = Turma.objects.values_list('ano_letivo', flat=True).distinct()
        for item in anos_banco:
            if item:
                try: anos_validos.append(int(item))
                except ValueError: pass
        
        anos_finais = sorted(list(set(anos_validos)), reverse=True)

        # Filtros de matrículas e indicadores de qualidade
        matriculas_do_ano = MatriculaTurma.objects.filter(turma__ano_letivo=ano_selecionado)
        total_geral = matriculas_do_ano.count()
        
        cursando = matriculas_do_ano.filter(status=StatusMatriculaTurma.CURSANDO).count()
        aprovados = matriculas_do_ano.filter(status=StatusMatriculaTurma.APROVADO).count()
        reprovados = matriculas_do_ano.filter(status=StatusMatriculaTurma.REPROVADO).count()
        
        if total_geral > 0:
            evasao_count = matriculas_do_ano.filter(
                status__in=[StatusMatriculaTurma.TRANSFERIDO, StatusMatriculaTurma.MATRICULA_EXCLUIDA]
            ).count()
            taxa_evasao = round((evasao_count / total_geral) * 100, 1)
        else:
            taxa_evasao = 0.0
        
        # DADOS FINANCEIROS DINÂMICOS DO BANCO:
        soma_real = ContratoFinanceiro.objects.filter(status='VIGENTE').aggregate(total=Sum('valor_total_empenhado'))['total'] or 0
        total_contratos_formatado = f"{soma_real:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        # Contagem total de contratos vigentes para o primeiro card
        total_vigentes = ContratoFinanceiro.objects.filter(status='VIGENTE').count()

        # =========================================================================
        # CÁLCULO REAL E DINÂMICO DAS MEDIÇÕES PENDENTES PARA O CARD AMARELO
        # =========================================================================
        soma_pendente = MedicaoContrato.objects.filter(status='PENDENTE').aggregate(total=Sum('valor_medido'))['total'] or 0
        total_pendente_formatado = f"{soma_pendente:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        # =========================================================================

        return {
            'cursando': cursando,
            'aprovados': aprovados,
            'reprovados': reprovados,
            'taxa_evasao': taxa_evasao,
            'total_contratos': total_contratos_formatado,
            'total_vigentes': total_vigentes,
            'medicoes_pendentes': total_pendente_formatado, # <-- Enviado com sucesso para o HTML
            'anos_disponiveis': anos_finais,
            'ano_selecionado': int(ano_selecionado),
        }

    def get(self, request, *args, **kwargs):
        """Renderiza a página quando o usuário entra para visualizar (GET)."""
        ano_atual = timezone.now().year
        ano_selecionado = request.GET.get('ano_letivo', str(ano_atual))
        
        context = self.get_context_data(request, ano_selecionado)
        context['form'] = ContratoFinanceiroForm()
        
        return render(request, 'atribuicao/indicadores.html', context)

    def post(self, request, *args, **kwargs):
        """Processa o salvamento quando o usuário envia o formulário (POST)."""
        form = ContratoFinanceiroForm(request.POST)
        if form.is_valid():
            form.save()  # Salva o novo contrato financeiro no banco de dados!
            return redirect(request.path)  # Recarrega a página limpa com os dados salvos
        
        # Caso o formulário falhe, recarrega a página exibindo os erros
        ano_atual = timezone.now().year
        ano_selecionado = request.GET.get('ano_letivo', str(ano_atual))
        context = self.get_context_data(request, ano_selecionado)
        context['form'] = form
        return render(request, 'atribuicao/indicadores.html', context)
