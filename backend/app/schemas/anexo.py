"""Schema de saída de Anexo."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AnexoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_tipo: str
    owner_id: int
    nome_arquivo: str
    categoria: Optional[str] = None
    content_type: Optional[str] = None
    tamanho_bytes: Optional[int] = None
    criado_em: Optional[datetime] = None
