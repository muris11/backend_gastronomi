from pydantic import BaseModel, Field
from typing import List, Optional, Union
from datetime import date

class RegisterRequest(BaseModel):
    username: str
    password: str
    nama_lengkap: str
    email: str
    no_telepon: str
    alamat: str

class ProfileUpdateRequest(BaseModel):
    nama_lengkap: str
    email: str
    no_telepon: str
    alamat: str

class PasswordUpdateRequest(BaseModel):
    password_lama: str
    password_baru: str

class VerifikasiUpdate(BaseModel):
    status: str
    barang_id: Optional[int] = None
    unit_kode: Optional[str] = None

class VerifikasiUpdateWithAlasan(VerifikasiUpdate):
    alasan_penolakan: Optional[str] = Field(None, max_length=500)

class PinjamRequest(BaseModel):
    nama_peminjam: str
    barang_id: Union[int, str]
    unit: str
    tanggal_pinjam: str
    tanggal_kembali: str
    keperluan: Optional[str] = None

class PeminjamanResponse(BaseModel):
    id: str
    nama: str
    nama_barang: str
    kategori_barang: str
    barang_id: Optional[int]
    tanggal_pinjam: str
    tanggal_kembali: str
    unit: str
    jumlah: int
    keperluan: str
    status: str
    assigned_units: List[str]
    tanggal_verifikasi: Optional[str] = None