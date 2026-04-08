from __future__ import annotations

from .store_files import StoreFileMixin
from .store_tickets import TicketStoreMixin


class Store(StoreFileMixin, TicketStoreMixin):
    pass


PlanfileStore = Store
