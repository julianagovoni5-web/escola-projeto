"""
cadastros/models.py

Módulo de domínio: Gestão de Cadastros.

Classes:
    Pessoa                  — dados cadastrais da pessoa física, com Endereco como VO embutido;
                              inclui identificação ampliada (FE 007/FE 008) e identificadores
                              específicos (RM, RA, CANAC — opcionais, null=True para não
                              conflitar entre si na constraint unique quando vazios). Também
                              guarda Título de Eleitor/Zona/Seção, E-mail 2, Telefone 2 e
                              Passaporte/Autorização de Permanência (esses dois últimos,
                              movidos de DadosDiscente em 03/09/2026 — a FE 008 mostra que
                              Docente também usa essa documentação, não é exclusiva de Discente).
    Disciplina               — nome/sigla únicos (3 letras, regex), cargas horárias
                              teórica/prática digitadas + carga do Programa de Instrução
                              aprovado pela ANAC; carga_horaria_total/hora_aula_* são
                              calculados (property); clean() bloqueia se a soma
                              teórica+prática não bater com o PI aprovado (05/09/2026,
                              ver docs/33 — risco real de não-conformidade com a ANAC).
    ConteudoProgramatico     — linhas do conteúdo programático de uma Disciplina; 'ordem'
                              é só organização de exibição, sem regra de negócio — é uma
                              trilha para o professor, não um trilho (docs/33).
    CatalogoComSigla         — base abstrata (sigla 3 letras única + regex, ativo),
                              compartilhada por Disciplina/SubModulo/Modulo (docs/33).
    SubModulo                — agrupa Disciplinas (via SubModuloDisciplina, M2M com
                              'ordem'); carga_horaria é calculada (soma das Disciplinas
                              vinculadas), nunca editável — não pode divergir do PI aprovado.
    SubModuloDisciplina      — tabela intermediária SubModulo×Disciplina, com 'ordem'
                              (uma Disciplina pode pertencer a mais de um SubModulo).
    Modulo                   — catálogo aberto (Básico, Especializado em Aviônica, etc.);
                              nome livre único + sigla (3 letras, usada em geração de PDF).
    ModuloSubModulo          — tabela intermediária Modulo×SubModulo, com 'ordem' (um
                              SubModulo pode pertencer a mais de um Módulo).
    OfertaModulo             — um Módulo oferecido num ano letivo; data_inicio obrigatória
                              no cadastro, data_fim só quando encerrada (mesmo padrão de
                              AtribuicaoFuncao); 'ativo' em vez de campo de situação.
    Turma                    — pertence a uma OfertaModulo (herda as datas dela); tem
                              periodo (Matutino/Vespertino/Noturno — pode variar entre
                              Turmas da mesma Oferta) e situacao própria.
    Ata                      — catálogo de Atas (Ordinária/Extraordinária × Início/
                              Término de Vínculo/Orientação/Conselho de Ensino/Outro,
                              eixos independentes); referenciada futuramente por
                              TurmaAluno (módulo Atribuição, ainda não implementado).
    CategoriaFuncao          — enum que classifica uma Funcao como Discente/Docente/Gestão,
                              usado pela interface para decidir qual formulário exibir
                              (não é regra de negócio — essa mora nas extensões, por estrutura).
    Funcao                   — catálogo aberto de cargos/funções (Diretor, Coordenador de
                              Curso de X, Docente, Discente, etc.); id + nome livre + categoria.
    VinculoFormal            — catálogo aberto de entidades de vínculo formal/contratual
                              (ex: FAPETI, PMT) — evita erro de digitação num dado repetido.
    AtribuicaoFuncao         — liga Pessoa a Funcao; dados comuns a qualquer atribuição
                              (situação, datas, ativo). Substitui o antigo Vinculo.
    HistoricoVinculoFormal   — histórico de VinculoFormal ao longo de uma AtribuicaoFuncao;
                              repetível (a entidade contratante pode mudar com o tempo).
                              Aplica-se só a categorias Docente e Gestão, nunca Discente.
    TipoPendencia            — enum dos tipos comuns de pendência documental no cadastro.
    PendenciaCadastro        — pendências de documentação física (certidão, RG, comprovante
                              de endereço, etc.), ligada a uma AtribuicaoFuncao. Universal:
                              aparece em Discente, Docente ou Gestão, sem restrição de
                              categoria — diferente de Formação/Experiência/Histórico, que
                              são condicionais. Usada para gerar o relatório operacional
                              de pendências por Turma/Aluno entregue ao Coordenador de Curso.
    DadosDiscente            — extensão de AtribuicaoFuncao (OneToOne) para Discente:
                              código de matrícula ANAC (específico do curso, diferente do
                              CANAC de Pessoa — ver nota no campo), contato de emergência,
                              responsável legal. Passaporte/Autorização de Permanência
                              vivem em Pessoa desde 03/09/2026 (uso compartilhado com
                              Docente, ver FE 008).
    DadosDocente             — extensão de AtribuicaoFuncao (OneToOne) para Docente;
                              inclui os Requisitos de Contratação da FE 008 (RBAC 141).
    FormacaoDocente          — Graduação/Formação Profissional/Aperfeiçoamento (FE 008,
                              seções 3/4/5), tabela única com campo tipo_formacao (DRY).
                              Guarda atualizado_em para futura detecção de FE 008 desatualizada.
    Capacidade               — aptidão de um DadosDocente para ministrar uma Disciplina;
                              referencia o FormacaoDocente que comprova a capacidade.
                              Guarda atualizado_em pelo mesmo motivo de FormacaoDocente.
    ExperienciaProfissional  — histórico profissional ligado a uma AtribuicaoFuncao,
                              relevante apenas para Funções de categoria Gestão (FOP 402).

Regras de negócio complexas ficam em services.py, não aqui.
"""
from django.utils import timezone
from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from django.core.validators import RegexValidator


@dataclass(frozen=True)
class Endereco:
    """Value Object — imutável, sem identidade própria, existe só em função de uma Pessoa."""
    cep: str
    logradouro: str
    numero: str
    complemento: str
    bairro: str
    cidade: str
    uf: str

    def __str__(self):
        return f"{self.logradouro}, {self.numero} - {self.bairro}, {self.cidade}/{self.uf}"


class Sexo(models.TextChoices):
    MASCULINO = 'M', 'Masculino'
    FEMININO = 'F', 'Feminino'


class RacaCor(models.TextChoices):
    BRANCA = 'BRANCA', 'Branca'
    PRETA = 'PRETA', 'Preta'
    AMARELA = 'AMARELA', 'Amarela'
    PARDA = 'PARDA', 'Parda'
    INDIGENA = 'INDIGENA', 'Indígena'
    NAO_DECLARADA = 'NAO_DECLARADA', 'Não Declarada'


class EstadoCivil(models.TextChoices):
    SOLTEIRO = 'SOLTEIRO', 'Solteiro(a)'
    CASADO = 'CASADO', 'Casado(a)'
    SEPARADO_JUDICIALMENTE = 'SEPARADO_JUDICIALMENTE', 'Separado(a) Judicialmente'
    DIVORCIADO = 'DIVORCIADO', 'Divorciado(a)'
    VIUVO = 'VIUVO', 'Viúvo(a)'


class Pessoa(models.Model):
    # Identificadores específicos (comuns a qualquer categoria).
    # null=True além de blank=True: quando vazio, salva NULL (não string vazia) —
    # múltiplos NULL não conflitam na constraint unique=True, diferente de múltiplas
    # strings vazias, que o SQLite trata como duplicatas entre si (causava IntegrityError
    # ao cadastrar duas Pessoas sem preencher RM, por exemplo).
    nome_completo = models.CharField(max_length=200)
    cpf = models.CharField(max_length=11, unique=True)
    data_nascimento = models.DateField()
    email = models.EmailField()
    telefone = models.CharField(max_length=20)
    registro_matricula = models.CharField(
        max_length=20, unique=True, blank=True, null=True, verbose_name="RM"
    )
    registro_aluno = models.CharField(
        max_length=20, unique=True, blank=True, null=True, verbose_name="RA"
    )
    codigo_anac = models.CharField(
        max_length=20, unique=True, blank=True, null=True, verbose_name="CANAC",
        help_text="Identificador da pessoa perante a ANAC. Idealmente obrigatório, mas "
                   "pode ficar pendente no cadastro inicial (ver PendenciaCadastro)."
    )

    # Identificação ampliada (FE 007 / FE 008)
    sexo = models.CharField(max_length=1, choices=Sexo.choices, blank=True)
    identidade = models.CharField(max_length=20, blank=True)
    data_emissao_identidade = models.DateField(null=True, blank=True)
    orgao_expedidor_identidade = models.CharField(max_length=20, blank=True)
    naturalidade = models.CharField(max_length=100, blank=True)
    uf_naturalidade = models.CharField(max_length=2, blank=True)
    nacionalidade = models.CharField(max_length=100, blank=True)
    filiacao_1 = models.CharField(max_length=200, blank=True)
    filiacao_2 = models.CharField(max_length=200, blank=True)
    nivel_instrucao = models.CharField(max_length=100, blank=True)
    estado_civil = models.CharField(max_length=30, choices=EstadoCivil.choices, blank=True)
    raca_cor = models.CharField(max_length=30, choices=RacaCor.choices, blank=True)

    # Título de Eleitor (FE 008, Docente) — lacuna aprovada na auditoria de 03/09/2026
    titulo_eleitor = models.CharField(max_length=12, blank=True, default='', verbose_name="Título de Eleitor")
    zona_eleitoral = models.CharField(max_length=3, blank=True, default='', verbose_name="Zona Eleitoral")
    secao_eleitoral = models.CharField(max_length=4, blank=True, default='', verbose_name="Seção Eleitoral")

    # E-mail 2 / Telefone 2 (FE 008 Docente / FOP 402 Gestão) — lacunas aprovadas em 03/09/2026
    email_2 = models.EmailField(blank=True, default='', verbose_name="E-mail 2")
    telefone_2 = models.CharField(max_length=20, blank=True, default='', verbose_name="Telefone 2 / Celular")

    # Passaporte / Autorização de Permanência — movidos de DadosDiscente para cá em
    # 03/09/2026 (auditoria de campos): a FE 008 mostra que Docente também usa essa
    # documentação quando estrangeiro, não é exclusiva de Discente como o modelo assumia.
    passaporte = models.CharField(max_length=20, blank=True, default='')
    autorizacao_permanencia = models.CharField(max_length=50, blank=True, default='')

    endereco_cep = models.CharField(max_length=8)
    endereco_logradouro = models.CharField(max_length=200)
    endereco_numero = models.CharField(max_length=10)
    endereco_complemento = models.CharField(max_length=100, blank=True)
    endereco_bairro = models.CharField(max_length=100)
    endereco_cidade = models.CharField(max_length=100)
    endereco_uf = models.CharField(max_length=2)

    ativo = models.BooleanField(default=True)

    @property
    def endereco(self) -> Endereco:
        return Endereco(
            cep=self.endereco_cep, logradouro=self.endereco_logradouro,
            numero=self.endereco_numero, complemento=self.endereco_complemento,
            bairro=self.endereco_bairro, cidade=self.endereco_cidade, uf=self.endereco_uf,
        )

    def atualizar_endereco(self, endereco: Endereco) -> None:
        self.endereco_cep = endereco.cep
        self.endereco_logradouro = endereco.logradouro
        self.endereco_numero = endereco.numero
        self.endereco_complemento = endereco.complemento
        self.endereco_bairro = endereco.bairro
        self.endereco_cidade = endereco.cidade
        self.endereco_uf = endereco.uf

    def __str__(self):
        return self.nome_completo


SIGLA_3_LETRAS_VALIDATOR = RegexValidator(
    regex=r'^[A-Z]{3}$',
    message="Sigla deve conter exatamente 3 letras maiúsculas (ex: CBA, PSO, TCX)."
)


class CatalogoComSigla(models.Model):
    """
    Base abstrata compartilhada por Disciplina/SubModulo/Modulo (mesma "forma":
    sigla de 3 letras única + regex, mais soft-deactivate via 'ativo') — evita
    repetir o validador e os campos em 3 lugares (decisão registrada em docs/33).
    """
    sigla = models.CharField(max_length=3, unique=True, validators=[SIGLA_3_LETRAS_VALIDATOR])
    ativo = models.BooleanField(default=True)

    class Meta:
        abstract = True


class Disciplina(CatalogoComSigla):
    """
    Cargas horárias em horas-relógio decimais (não "tempos de aula"). A carga total
    (teórica + prática) precisa bater exatamente com o Programa de Instrução aprovado
    pela ANAC — divergência aqui pode gerar notificação da ANAC à escola, por isso a
    trava é em clean() (ver nota abaixo sobre importação em lote).
    """
    nome = models.CharField(max_length=100, unique=True)
    carga_horaria_programa_de_instrucao = models.DecimalField(
        max_digits=6, decimal_places=2,
        help_text="Valor fixo, definido no Programa de Instrução aprovado pela ANAC."
    )
    carga_horaria_teorica = models.DecimalField(max_digits=6, decimal_places=2)
    carga_horaria_pratica = models.DecimalField(max_digits=6, decimal_places=2)

    @property
    def carga_horaria_total(self):
        return self.carga_horaria_teorica + self.carga_horaria_pratica

    @property
    def hora_aula_total(self):
        """1 hora-aula = 45 minutos = 0,75h."""
        return self.carga_horaria_total / Decimal('0.75')

    @property
    def hora_aula_teorica(self):
        return self.carga_horaria_teorica / Decimal('0.75')

    @property
    def hora_aula_pratica(self):
        return self.carga_horaria_pratica / Decimal('0.75')

    def clean(self):
        if self.carga_horaria_total != self.carga_horaria_programa_de_instrucao:
            raise ValidationError(
                f"Carga horária total (teórica {self.carga_horaria_teorica}h + prática "
                f"{self.carga_horaria_pratica}h = {self.carga_horaria_total}h) não bate "
                f"com o Programa de Instrução aprovado ({self.carga_horaria_programa_de_instrucao}h)."
            )

    def __str__(self):
        return f"{self.sigla} - {self.nome}"


class ConteudoProgramatico(models.Model):
    """
    Uma linha/tópico do conteúdo programático de uma Disciplina. 'ordem' é só para
    organizar a exibição no cadastro — o Conteúdo Programático é uma trilha para o
    professor, não um trilho: o instrutor decide a sequência real de ensino conforme
    a turma (conhecimentos prévios, lacunas cognitivas), sem nenhuma regra de negócio
    amarrada a 'ordem' (confirmado em 05/09/2026, ver docs/33).

    on_delete=PROTECT (não CASCADE): impede excluir uma Disciplina que já tenha
    Conteúdo Programático cadastrado — preserva rastreabilidade do que foi definido
    para ser ministrado; força desativar (Disciplina.ativo=False) em vez de apagar.
    """
    disciplina = models.ForeignKey(Disciplina, on_delete=models.PROTECT, related_name='conteudos_programaticos')
    ordem = models.PositiveSmallIntegerField()
    descricao = models.TextField()
    observacao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['disciplina', 'ordem'], name='unique_ordem_por_disciplina'),
        ]

    def __str__(self):
        return f"{self.disciplina.sigla} #{self.ordem} - {self.descricao[:50]}"


class SubModulo(CatalogoComSigla):
    """
    carga_horaria é CALCULADA (soma das Disciplinas vinculadas via SubModuloDisciplina),
    nunca editável manualmente — não pode divergir do Programa de Instrução aprovado,
    já que o valor calculado É o valor oficial (decisão de 05/09/2026, ver docs/33).
    """
    nome = models.CharField(max_length=150)

    @property
    def carga_horaria(self):
        total = Decimal('0')
        for vinculo in self.disciplinas_vinculadas.select_related('disciplina'):
            total += vinculo.disciplina.carga_horaria_total
        return total

    def __str__(self):
        return f"{self.sigla} - {self.nome}"


class SubModuloDisciplina(models.Model):
    """Tabela intermediária: quais Disciplinas compõem um SubModulo, e em que ordem (só organização, sem regra de negócio)."""
    submodulo = models.ForeignKey(SubModulo, on_delete=models.PROTECT, related_name='disciplinas_vinculadas')
    disciplina = models.ForeignKey(Disciplina, on_delete=models.PROTECT, related_name='submodulos_vinculados')
    ordem = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['submodulo', 'disciplina'], name='unique_disciplina_por_submodulo'),
            models.UniqueConstraint(fields=['submodulo', 'ordem'], name='unique_ordem_disciplina_por_submodulo'),
        ]

    def __str__(self):
        return f"{self.submodulo.sigla} - {self.disciplina.sigla} (#{self.ordem})"


class CategoriaModulo(models.TextChoices):
    """
    Estruturado (07/09/2026, docs/37) — usado pela regra de negócio do módulo
    Atribuição para decidir se encerrar uma Turma daquele Módulo fecha o
    vínculo institucional do Discente (Especializado) ou não (Básico/
    Extracurricular). Independente de 'nome', que continua livre.
    """
    BASICO = 'BASICO', 'Básico'
    ESPECIALIZADO = 'ESPECIALIZADO', 'Especializado'
    EXTRACURRICULAR = 'EXTRACURRICULAR', 'Extracurricular'


class Modulo(CatalogoComSigla):
    """
    Catálogo aberto — Básico, Especializado em Aviônica, Especializado em Célula,
    Especializado em GMP, Extracurricular. 'nome' é texto cadastrado, livre, não
    choices (permite criar novos Módulos sem alterar código). 'sigla' usada em
    geração futura de PDFs (hábito da escola), ex: "2026 BAS NOT R3 MAT".
    'categoria' é estruturado (ver CategoriaModulo) — não confundir com 'nome'.
    """
    nome = models.CharField(max_length=150, unique=True)
    categoria = models.CharField(max_length=20, choices=CategoriaModulo.choices)
    descricao = models.TextField(blank=True)

    @property
    def carga_horaria(self):
        """Soma das cargas horárias (já calculadas) dos SubModulos vinculados via ModuloSubModulo."""
        total = Decimal('0')
        for vinculo in self.submodulos_vinculados.select_related('submodulo'):
            total += vinculo.submodulo.carga_horaria
        return total

    def __str__(self):
        return f"{self.sigla} - {self.nome}"


class ModuloSubModulo(models.Model):
    """Tabela intermediária: quais SubModulos compõem um Modulo, e em que ordem (só organização, sem regra de negócio)."""
    modulo = models.ForeignKey(Modulo, on_delete=models.PROTECT, related_name='submodulos_vinculados')
    submodulo = models.ForeignKey(SubModulo, on_delete=models.PROTECT, related_name='modulos_vinculados')
    ordem = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['modulo', 'submodulo'], name='unique_submodulo_por_modulo'),
            models.UniqueConstraint(fields=['modulo', 'ordem'], name='unique_ordem_submodulo_por_modulo'),
        ]

    def __str__(self):
        return f"{self.modulo.sigla} - {self.submodulo.sigla} (#{self.ordem})"


class OfertaModulo(models.Model):
    """
    Um Modulo oferecido num ano letivo específico. Mesmo padrão de AtribuicaoFuncao:
    'data_inicio' obrigatória no cadastro, 'data_fim' só preenchida ao encerrar
    (tela/popup futura); 'ativo' substitui um campo de situação separado.
    """
    modulo = models.ForeignKey(Modulo, on_delete=models.PROTECT, related_name='ofertas')
    ano_letivo = models.PositiveSmallIntegerField()
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)
    ativo = models.BooleanField(default=True)
    observacao = models.TextField(blank=True)

    def __str__(self):
        return f"{self.modulo.nome} {self.ano_letivo}"


class PeriodoTurma(models.TextChoices):
    MATUTINO = 'MATUTINO', 'Matutino'
    VESPERTINO = 'VESPERTINO', 'Vespertino'
    NOTURNO = 'NOTURNO', 'Noturno'


class SituacaoTurma(models.TextChoices):
    PLANEJADA = 'PLANEJADA', 'Planejada'
    EM_ANDAMENTO = 'EM_ANDAMENTO', 'Em Andamento'
    ENCERRADA = 'ENCERRADA', 'Encerrada'


# LOCALIZAÇÃO: cadastros/models.py

class StatusTurma(models.TextChoices):
    PLANEJADA = 'PLANEJADA', 'Planejada'
    EM_ANDAMENTO = 'EM_ANDAMENTO', 'Em Andamento'
    CONCLUIDA = 'CONCLUIDA', 'Concluída'

class Turma(models.Model):
    nome = models.CharField(max_length=50)
    sigla = models.CharField(max_length=10, blank=True, null=True)
    periodo = models.CharField(max_length=20, blank=True, null=True) # Ex: Matutino, Noturno
    observacao = models.TextField(blank=True, null=True)
    
    # NOVOS CAMPOS PARA ATENDER O DASHBOARD:
    status = models.CharField(
        max_length=20, 
        choices=StatusTurma.choices, 
        default=StatusTurma.PLANEJADA, 
        db_index=True # Indexado para deixar a busca do dashboard ultra rápida
    )
    ano_letivo = models.PositiveIntegerField(
        default=2026, 
        db_index=True # Indexado para filtrar o ano corrente no painel
    )

    def __str__(self):
        return f"{self.nome} ({self.ano_letivo}) - {self.get_status_display()}"


class TipoAta(models.TextChoices):
    ORDINARIA = 'ORDINARIA', 'Ordinária'
    EXTRAORDINARIA = 'EXTRAORDINARIA', 'Extraordinária'


class FinalidadeAta(models.TextChoices):
    INICIO_VINCULO = 'INICIO_VINCULO', 'Início de Vínculo'
    TERMINO_VINCULO = 'TERMINO_VINCULO', 'Término de Vínculo'
    ORIENTACAO = 'ORIENTACAO', 'Orientação'
    CONSELHO_ENSINO = 'CONSELHO_ENSINO', 'Conselho de Ensino'
    OUTRO = 'OUTRO', 'Outro'


class Ata(models.Model):
    """
    Catálogo independente — 'tipo' e 'finalidade' são eixos independentes (uma Ata
    de finalidade Término de Vínculo pode ser tipo Ordinária ou Extraordinária).
    Sem 'ativo': uma Ata é, por natureza, um registro histórico fechado. Referenciada
    futuramente por TurmaAluno.ata_inicio/ata_termino (módulo Atribuição, não
    implementado ainda) — não tem campo de motivo aqui de propósito.

    'numero' é opcional no formulário: se deixado em branco, é gerado
    automaticamente em save() — sequencial de 3 dígitos, reiniciado a cada ano
    (o ano de 'data', não o ano do sistema), numa série própria por 'tipo'
    (Ordinária e Extraordinária nunca competem pelo mesmo número). Corrige um
    bug real de 05/09/2026: 'numero' sozinho como unique=True impedia duas
    Atas de tipos diferentes terem o mesmo número no mesmo ano — a constraint
    certa é composta (numero, tipo). Preenchimento manual continua permitido
    (ex: corrigir um número, ou migrar numeração de um sistema antigo).
    """
    numero = models.CharField(
        max_length=20, blank=True,
        help_text="Deixe em branco para gerar automaticamente (3 dígitos/ano, por tipo)."
    )
    tipo = models.CharField(max_length=20, choices=TipoAta.choices)
    finalidade = models.CharField(max_length=20, choices=FinalidadeAta.choices)
    data = models.DateField()
    assunto = models.CharField(max_length=255, blank=True)
    observacao = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['numero', 'tipo'], name='unique_numero_por_tipo'),
        ]

    def save(self, *args, **kwargs):
        if not self.numero:
            ano = self.data.year
            sequencial = Ata.objects.filter(tipo=self.tipo, data__year=ano).count() + 1
            self.numero = f"{sequencial:03d}/{ano}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Ata {self.get_tipo_display()} {self.numero} - {self.get_finalidade_display()}"


class AtaPessoa(models.Model):
    """
    Vincula uma Pessoa (Discente) a uma Ata — mesmo espírito de
    ModuloSubModulo/SubModuloDisciplina: vínculo sem estado, sem data própria.

    EXCEÇÃO PROVISÓRIA ao princípio "Pessoa amarrada = módulo Atribuição"
    (docs/29): implementada aqui em 05/09/2026 só para destravar o uso real de
    Ata de Conselho/Orientação/Outro antes do módulo Atribuição existir.
    Confirmado com a pessoa responsável que este Model MIGRA para o módulo
    Atribuição quando ele for construído — não é definitivo em cadastros
    (ver docs/35).
    """
    ata = models.ForeignKey(Ata, on_delete=models.PROTECT, related_name='pessoas_vinculadas')
    pessoa = models.ForeignKey(Pessoa, on_delete=models.PROTECT, related_name='atas_vinculadas')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['ata', 'pessoa'], name='unique_pessoa_por_ata'),
        ]

    def __str__(self):
        return f"{self.ata.numero} - {self.pessoa.nome_completo}"


class CategoriaFuncao(models.TextChoices):
    """
    Classifica uma Funcao para fins de interface (qual formulário/extensão exibir).
    NÃO é usado para regra de negócio — isso continua sendo decidido pela existência
    estrutural de DadosDiscente/DadosDocente, nunca por este campo nem pelo nome da Funcao.
    """
    DISCENTE = 'DISCENTE', 'Discente'
    DOCENTE = 'DOCENTE', 'Docente'
    GESTAO = 'GESTAO', 'Gestão'


class Funcao(models.Model):
    """Catálogo aberto: id + nome livre + categoria (para a interface saber qual formulário exibir)."""
    nome = models.CharField(max_length=100, unique=True)
    categoria = models.CharField(max_length=10, choices=CategoriaFuncao.choices)

    def __str__(self):
        return self.nome


class RequisitoContratacao(models.TextChoices):
    """Critério de contratação (RBAC 141), aplicável a Docente e Gestão — escolha única."""
    EXPERIENCIA_DOCENTE = 'EXPERIENCIA_DOCENTE', 'Experiência docente comprovada (6 meses geral + 6 meses na área específica)'
    FORMACAO_ESPECIFICA = 'FORMACAO_ESPECIFICA', 'Formação específica na área de atuação'
    OUTRO = 'OUTRO', 'Outro'


class SituacaoAtribuicao(models.TextChoices):
    ATIVO = 'ATIVO', 'Ativo'
    INATIVO = 'INATIVO', 'Inativo'

class AtribuicaoFuncaoQuerySet(models.QuerySet):
    def ativos(self):
        """Retorna apenas as atribuições com situação ATIVA."""
        return self.filter(situacao=SituacaoAtribuicao.ATIVO)

    def apenas_instrutores(self):
        """Filtra apenas docentes/gestão, excluindo discentes de forma segura."""
        return self.ativos().select_related('pessoa', 'funcao').exclude(
            funcao__nome__icontains='aluno'
        ).exclude(
            funcao__nome__icontains='discente'
        ).order_by('pessoa__nome_completo')

class AtribuicaoFuncao(models.Model):
    """
    'situacao' consolidada em 07/09/2026 (docs/37, Etapa 0): antes havia dois
    campos redundantes (situacao texto livre + ativo booleano), nenhum
    editável por tela nenhuma até então. Agora é um único campo binário —
    a distinção fina para Discente (Aguardando Atribuição/Aguardando Turma)
    é calculada na exibição a partir de MatriculaTurma (módulo atribuicao),
    nunca gravada aqui. Sem campo de Ata: a Ata de encerramento de um
    Discente vive em MatriculaTurma.ata_encerramento, não aqui.
    """
    objects = AtribuicaoFuncaoQuerySet.as_manager()
    pessoa = models.ForeignKey(Pessoa, on_delete=models.CASCADE, related_name='atribuicoes')
    funcao = models.ForeignKey(Funcao, on_delete=models.PROTECT, related_name='atribuicoes')
    situacao = models.CharField(max_length=10, choices=SituacaoAtribuicao.choices, default=SituacaoAtribuicao.ATIVO)
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)
    requisito_contratacao = models.CharField(
        max_length=30, choices=RequisitoContratacao.choices, blank=True,
        help_text="Aplicável a Docente e Gestão (RBAC 141) — não relevante para Discente."
    )
    documento_comprobatorio = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.pessoa.nome_completo} - {self.funcao.nome}"


class HistoricoVinculoFormal(models.Model):
    """
    Histórico de VinculoFormal ao longo de uma AtribuicaoFuncao — repetível, porque a
    entidade contratante pode mudar com o tempo sem que a pessoa mude de Função na escola
    (ex: FAPETI de 2025 a 2026, depois FUSSUSS a partir de 2026, em aberto).
    """
    atribuicao = models.ForeignKey(AtribuicaoFuncao, on_delete=models.CASCADE, related_name='historico_vinculo_formal')
    vinculo_formal = models.ForeignKey('cadastros.VinculoFormal', on_delete=models.CASCADE)
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)
    observacao = models.TextField(
        blank=True,
        help_text="Contexto ou correção de erro de cadastro — não há exclusão de um "
                   "Histórico de Vínculo Formal, só encerramento (preencher data_fim)."
    )

    def __str__(self):
        return f"{self.vinculo_formal.nome} ({self.data_inicio} - {self.data_fim or 'atual'})"


class TipoPendencia(models.TextChoices):
    """Tipos comuns de pendência documental — 'OUTRO' + descricao cobre casos incomuns."""
    CANAC = 'CANAC', 'CANAC'
    RM = 'RM', 'Registro de Matrícula'
    RA = 'RA', 'Registro de Aluno'
    CODIGO_MATRICULA_ANAC = 'CODIGO_MATRICULA_ANAC', 'Código de Matrícula ANAC'
    CERTIDAO_NASCIMENTO = 'CERTIDAO_NASCIMENTO', 'Certidão de Nascimento'
    CPF_FISICO = 'CPF_FISICO', 'CPF (documento físico)'
    RG = 'RG', 'RG/Carteira de Identidade'
    PASSAPORTE = 'PASSAPORTE', 'Passaporte + Autorização de Permanência (estrangeiro)'
    COMPROVANTE_ENDERECO = 'COMPROVANTE_ENDERECO', 'Comprovante de Endereço'
    CARTAO_VACINA = 'CARTAO_VACINA', 'Cartão de Vacina (menor de 18)'
    OUTRO = 'OUTRO', 'Outro'


class PendenciaCadastro(models.Model):
    """
    Pendências de documentação física do cadastro — universal, aparece em Discente,
    Docente ou Gestão (diferente de Formação/Experiência/Histórico, que são condicionais
    por categoria). Ligada a AtribuicaoFuncao, não a Pessoa, pensando no relatório
    operacional futuro (Turma -> Aluno -> Pendências) entregue ao Coordenador de Curso.
    """
    atribuicao = models.ForeignKey(AtribuicaoFuncao, on_delete=models.CASCADE, related_name='pendencias')
    tipo = models.CharField(max_length=30, choices=TipoPendencia.choices)
    descricao = models.CharField(
        max_length=200, blank=True,
        help_text="Detalhe livre, usado sobretudo quando tipo=OUTRO."
    )
    resolvida = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)
    resolvida_em = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.atribuicao.pessoa.nome_completo}"


class DadosDiscente(models.Model):
    atribuicao = models.OneToOneField(AtribuicaoFuncao, on_delete=models.CASCADE, related_name='dados_discente')

    # Diferente de Pessoa.codigo_anac (identifica a PESSOA perante a ANAC, permanente):
    # este é o código da MATRÍCULA específica (ex: 239.MCELT.25.00115 — Ciac.Habilitação.
    # Ano.Sequencial), muda a cada novo curso. Pode ficar pendente no cadastro inicial
    # (ver PendenciaCadastro, tipo CODIGO_MATRICULA_ANAC) até a ANAC processar.
    codigo_matricula_anac = models.CharField(
        max_length=20, unique=True, blank=True, null=True,
        verbose_name="Código de Matrícula ANAC"
    )

    # Contato de emergência ("quem avisar") — texto simples, sem entidade própria
    contato_emergencia_nome = models.CharField(max_length=200, blank=True)
    contato_emergencia_parentesco = models.CharField(max_length=50, blank=True)
    contato_emergencia_telefone = models.CharField(max_length=20, blank=True)
    contato_emergencia_endereco = models.CharField(max_length=300, blank=True)

    # Responsável legal (só se menor de idade) — texto simples, reaproveitado nas assinaturas do FE 007
    responsavel_nome = models.CharField(max_length=200, blank=True)
    responsavel_endereco = models.CharField(max_length=300, blank=True)
    responsavel_identidade = models.CharField(max_length=20, blank=True)
    responsavel_orgao_expedidor = models.CharField(max_length=20, blank=True)
    responsavel_data_emissao = models.DateField(null=True, blank=True)
    responsavel_qualificacao = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.atribuicao.pessoa.nome_completo} - Dados Discente"


class DadosDocente(models.Model):
    atribuicao = models.OneToOneField(AtribuicaoFuncao, on_delete=models.CASCADE, related_name='dados_docente')

    # Requisitos de Contratação (FE 008, seção 6, RBAC 141)
    experiencia_docente_comprovada = models.TextField(
        blank=True,
        help_text="Análise de declarações de serviço, CV, etc. — comprovação de experiência docente (RBAC 141)."
    )
    formacao_especifica_comprobatoria = models.ForeignKey(
        'FormacaoDocente', on_delete=models.PROTECT, null=True, blank=True,
        related_name='comprova_requisito_para',
        help_text="Curso que comprova formação específica na área de atuação (RBAC 141)."
    )

    def __str__(self):
        return f"{self.atribuicao.pessoa.nome_completo} - Dados Docente"

    def possui_treinamento_valido(self) -> bool:
        return True


class TipoFormacaoDocente(models.TextChoices):
    GRADUACAO = 'GRADUACAO', 'Graduação'
    FORMACAO_PROFISSIONAL = 'FORMACAO_PROFISSIONAL', 'Formação Profissional'
    APERFEICOAMENTO_PROFISSIONAL = 'APERFEICOAMENTO_PROFISSIONAL', 'Aperfeiçoamento Profissional'


class FormacaoDocente(models.Model):
    """
    Graduação/Formação Profissional/Aperfeiçoamento (FE 008, seções 3/4/5) — tabela única
    com campo tipo_formacao, evitando 3 Models quase idênticos (DRY).

    'atualizado_em' guarda quando este registro mudou pela última vez — não usado ainda,
    mas preparado para a futura funcionalidade de alertar quando a FE 008 impressa ficar
    desatualizada em relação ao banco (numeração "4.1" etc. é calculada, pode mudar com
    edições; ver item de Backlog "Alerta de FE 008 desatualizada").
    """
    dados_docente = models.ForeignKey(DadosDocente, on_delete=models.CASCADE, related_name='formacoes')
    tipo_formacao = models.CharField(max_length=30, choices=TipoFormacaoDocente.choices)
    curso = models.CharField(max_length=200)
    entidade = models.CharField(max_length=200)
    cidade = models.CharField(max_length=100)
    uf = models.CharField(max_length=2)
    ano_conclusao = models.IntegerField()
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.curso} ({self.get_tipo_formacao_display()})"


class Capacidade(models.Model):
    """'atualizado_em': mesmo propósito de FormacaoDocente.atualizado_em, ver docstring acima."""
    dados_docente = models.ForeignKey(DadosDocente, on_delete=models.CASCADE, related_name='capacidades')
    disciplina = models.ForeignKey(Disciplina, on_delete=models.PROTECT, related_name='capacidades')
    formacao_comprobatoria = models.ForeignKey(
        FormacaoDocente, on_delete=models.PROTECT, null=True, blank=True,
        help_text="Curso (FormacaoDocente) que comprova a capacidade de ministrar esta disciplina."
    )
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)
    ativo = models.BooleanField(default=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['dados_docente', 'disciplina'],
                condition=models.Q(ativo=True),
                name='unique_capacidade_ativa'
            )
        ]

class ExperienciaProfissional(models.Model):
    """Registra a bagagem do colaborador em outras instituições antes da EMCA."""
    pessoa = models.ForeignKey('Pessoa', on_delete=models.CASCADE, related_name='experiencias_profissionais', default=1)
    organizacao = models.CharField(max_length=255, verbose_name="Instituição/Empresa")
    cargo = models.CharField(max_length=100, verbose_name="Cargo/Função")
    data_inicio = models.DateField(verbose_name="Data de Início", default=timezone.now)
    data_fim = models.DateField(null=True, blank=True, verbose_name="Data de Fim")

    class Meta:
        verbose_name = "Experiência Profissional"
        verbose_name_plural = "Experiências Profissionais"
        ordering = ['-data_inicio']

    def __str__(self):
        return f"{self.cargo} em {self.organizacao}"


class VinculoFormal(models.Model):
    """Registra a evolução contratual e portarias do funcionário dentro da EMCA."""
    pessoa = models.ForeignKey('Pessoa', on_delete=models.CASCADE, related_name='vinculos_formais', default=1)
    tipo_vinculo = models.CharField(max_length=100, verbose_name="Tipo de Vínculo", default="Não Informado")  
    numero_documento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Número do Documento/Portaria")
    carga_horaria = models.PositiveIntegerField(verbose_name="Carga Horária Semanal", default=40)
    data_admissao = models.DateField(verbose_name="Data de Admissão", default=timezone.now)
    data_rescisao = models.DateField(null=True, blank=True, verbose_name="Data de Rescisão/Desligamento")

    class Meta:
        verbose_name = "Histórico de Vínculo Formal"
        verbose_name_plural = "Históricos de Vínculos Formais"
        ordering = ['-data_admissao']
        

    def __str__(self):
        return f"{self.tipo_vinculo} - {self.numero_documento or 'Sem Nº'}"
