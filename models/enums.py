from enum import Enum

class KondisiBarang(str, Enum):
    BAIK = "Baik"
    RUSAK_RINGAN = "Rusak Ringan"
    RUSAK_BERAT = "Rusak Berat"
    HILANG = "Hilang"
    PERLU_PERBAIKAN = "Perlu Perbaikan"

class StatusPeminjaman(str, Enum):
    MENUNGGU = "Menunggu"
    DISETUJUI = "Disetujui"
    DITOLAK = "Ditolak"
    DIPINJAM = "Dipinjam"
    SELESAI = "Selesai"
    MENUNGGU_VERIFIKASI_PENGEMBALIAN = "Menunggu Verifikasi Pengembalian"

class StatusUnit(str, Enum):
    TERSEDIA = "Tersedia"
    MENUNGGU = "Menunggu"
    DIPINJAM = "Dipinjam"
    RUSAK = "Rusak"