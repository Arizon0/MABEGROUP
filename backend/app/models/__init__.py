"""Models do ERP. Importar tudo aqui para o Alembic enxergar o metadata."""
from .anexo import Anexo
from .base import Base
from .compra import ItemPedidoCompra, PedidoCompra
from .custos_venda import AdsInvestimento, AliquotaImposto
from .dre import DespesaDRE
from .estoque import EstoqueSaldo, Local, MovimentoEstoque
from .financeiro import ContaPagar, ContaReceber
from .fornecedor import ContatoFornecedor, Fornecedor
from .produto import Produto
from .sku_map import SkuMap, SkuPendencia
from .usuario import Usuario
from .venda import Venda

__all__ = [
    "Base",
    "Usuario",
    "Produto",
    "Fornecedor",
    "ContatoFornecedor",
    "Anexo",
    "Local",
    "EstoqueSaldo",
    "MovimentoEstoque",
    "PedidoCompra",
    "ItemPedidoCompra",
    "ContaPagar",
    "ContaReceber",
    "DespesaDRE",
    "SkuMap",
    "SkuPendencia",
    "Venda",
    "AliquotaImposto",
    "AdsInvestimento",
]
