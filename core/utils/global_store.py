import asyncio

# Struktur data untuk menyimpan jumlah rumput yang ditambang
mined_grass_counts = {}
# Lock untuk menghindari race condition
lock = asyncio.Lock()