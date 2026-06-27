"""Models do ERP. Importar tudo aqui para o Alembic enxergar o metadata."""
from .anexo import Anexo
from .base import Base
from .fornecedor import ContatoFornecedor, Fornecedor
from .produto import Produto
from .sku_map import SkuMap, SkuPendencia
from .venda import Venda

__all__ = [
    "Base",
    "Produto",
    "Fornecedor",
    "ContatoFornecedor",
    "Anexo",
    "SkuMap",
    "SkuPendencia",
    "Venda",
]
