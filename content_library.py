# -*- coding: utf-8 -*-
"""
Curated Library of Bengali Literature.
Contains authentic, rich excerpts from renowned Bengali authors:
- Rabindranath Tagore
- Kazi Nazrul Islam
- Humayun Ahmed
- Sunil Gangopadhyay
- Shirshendu Mukhopadhyay
- Jibanananda Das
- Helal Hafiz
- Rudra Mohammad Shahidullah
- Joy Goswami
- Contemporary / Trending writers (Sadat Hossain, Modern youth reflections)

Every excerpt strictly contains >= 500 Bengali words.
"""

from items_humayun import HUMAYUN_ITEMS
from items_rabindranath import RABINDRANATH_ITEMS
from items_nazrul import NAZRUL_ITEMS
from items_sunil import SUNIL_ITEMS
from items_jibanananda import JIBANANANDA_ITEMS
from items_shirshendu import SHIRSHENDU_ITEMS
from items_helal_hafiz import HELAL_HAFIZ_ITEMS
from items_rudra import RUDRA_ITEMS
from items_joy_goswami import JOY_GOSWAMI_ITEMS
from items_contemporary import CONTEMPORARY_ITEMS

LITERATURE_ITEMS = (
    HUMAYUN_ITEMS
    + RABINDRANATH_ITEMS
    + NAZRUL_ITEMS
    + SUNIL_ITEMS
    + JIBANANANDA_ITEMS
    + SHIRSHENDU_ITEMS
    + HELAL_HAFIZ_ITEMS
    + RUDRA_ITEMS
    + JOY_GOSWAMI_ITEMS
    + CONTEMPORARY_ITEMS
)
