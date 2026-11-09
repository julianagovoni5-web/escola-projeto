from django.views.generic import TemplateView

class CentralRelatoriosView(TemplateView):
    """View central da secretaria para exibição de relatórios e dados institucionais."""
    template_name = 'atribuicao/relatorios.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ano_atual = timezone.now().year
        
        # Imports locais seguros
        from cadastros.models import AtribuicaoFuncao, Turma, Pessoa
        from atribuicao.models import MatriculaTurma, StatusMatriculaTurma, RegistroInstrucao
        from django.db.models import Q, Sum
        
        # 1. Busca para o menu lateral
        context['instrutores'] = AtribuicaoFuncao.objects.select_related('pessoa').exclude(
            Q(funcao__nome__icontains='aluno') | 
            Q(funcao__nome__icontains='discente')
        ).order_by('pessoa__nome_completo')
        
        # 2. CARD 1: Total de Horas Ministradas (Soma real das aulas gravadas)
        horas_sub = RegistroInstrucao.objects.aggregate(total=Sum('carga_horaria'))['total'] or 0
        context['total_horas'] = f"{horas_sub:.0f}h"

        # 3. CARD 2: Matrículas Ativas (Alunos ativos cadastrados no sistema)
        context['total_matriculas'] = Pessoa.objects.filter(
            ativo=True, 
            atribuicoes__funcao__categoria='DISCENTE'
        ).distinct().count()

        # 4. CARD 3: Total de Atribuições (Turmas em andamento no ano atual)
        context['total_atribuicoes'] = Turma.objects.filter(
            status='EM_ANDAMENTO', 
            ano_letivo=ano_atual
        ).count()
        
        return context
    
import os
from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from xhtml2pdf import pisa  # Nova biblioteca nativa em Python

class ExportarRelatorioPDFView(LoginRequiredMixin, View):
    """Gera um relatório institucional em PDF usando xhtml2pdf de forma nativa no Windows."""
    
    def get(self, request, *args, **kwargs):
        ano_atual = timezone.now().year
        
        # 1. Coleta os dados analíticos
        from cadastros.models import Turma, Pessoa
        from atribuicao.models import ContratoFinanceiro, MatriculaTurma, StatusMatriculaTurma
        from django.db.models import Count, Sum

        financeiro = ContratoFinanceiro.objects.filter(status='VIGENTE').aggregate(
            total_empenhado=Sum('valor_total_empenhado'),
            total_contratos=Count('id')
        )

        secretaria = {
            'total_alunos': Pessoa.objects.filter(ativo=True, atribuicoes__funcao__categoria='DISCENTE').distinct().count(),
            'evadidos_ano': MatriculaTurma.objects.filter(
                status__in=[StatusMatriculaTurma.TRANSFERIDO, StatusMatriculaTurma.MATRICULA_EXCLUIDA],
                turma__ano_letivo=ano_atual
            ).count(),
            'aprovados_ano': MatriculaTurma.objects.filter(
                status=StatusMatriculaTurma.APROVADO,
                turma__ano_letivo=ano_atual
            ).count()
        }

        coordenacao = {
            'turmas_ativas': Turma.objects.filter(status='EM_ANDAMENTO', ano_letivo=ano_atual).count(),
            'turmas_planejadas': Turma.objects.filter(status='PLANEJADA', ano_letivo=ano_atual).count()
        }

        # 2. Contexto injetado no HTML
        context = {
            'ano_letivo': ano_atual,
            'financeiro': financeiro,
            'secretaria': secretaria,
            'coordenacao': coordenacao,
            'data_geracao': timezone.now().strftime('%d/%m/%Y %H:%M')
        }

        # 3. Renderiza o HTML em string
        html_string = render_to_string('relatorios/pdf_template.html', context)
        
        # 4. Cria a estrutura da resposta HTTP para o PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="relatorio_institucional_{ano_atual}.pdf"'
        
        # 5. Converte o HTML em PDF direto para a resposta do navegador
        pisa_status = pisa.CreatePDF(html_string, dest=response)
        
        # Se ocorrer algum erro na geração, retorna um erro amigável
        if pisa_status.err:
            return HttpResponse('Erro ao gerar o relatório em PDF', status=500)
            
        return response