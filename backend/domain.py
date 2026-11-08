"""Regras do estoque, independentes dos serviços da AWS."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
import unicodedata
from uuid import UUID

UNITS = ('caixotes', 'sacos', 'meiao', 'bags')
ROLES = ('admin', 'operator', 'viewer')

class AppError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message

def normalized(value):
    text = unicodedata.normalize('NFD', value)
    return ' '.join(''.join(c for c in text if not unicodedata.combining(c)).lower().split())

def text(value, name, limit, required=False):
    if not isinstance(value, str):
        raise AppError(400, f'{name}: informe um texto válido.')
    value = value.strip()
    if len(value) > limit or (required and not value):
        raise AppError(400, f'{name}: confira o preenchimento (até {limit} caracteres).')
    return value

def record_key(quality, size):
    return hashlib.sha256((normalized(quality)+'|'+str(size)).encode()).hexdigest()

def validate_record(body, kind):
    if not isinstance(body, dict) or kind not in ('entries', 'exits'):
        raise AppError(400, 'Registro inválido.')
    try:
        record_id = str(UUID(str(body.get('id', ''))))
    except ValueError:
        raise AppError(400, 'Identificador do registro inválido.')
    size = str(body.get('size', ''))
    if size not in ('1', '2', '3'):
        raise AppError(400, 'Escolha o tamanho 1, 2 ou 3.')
    quality = ' '.join(text(body.get('quality', ''), 'Qualidade', 80, True).split())
    date = body.get('date', '')
    pattern = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}' if kind == 'entries' else r'\d{4}-\d{2}-\d{2}'
    try:
        if not isinstance(date, str) or not re.fullmatch(pattern, date): raise ValueError()
        datetime.fromisoformat(date)
    except ValueError:
        raise AppError(400, 'Informe uma data válida.')
    result = {'id': record_id, 'quality': quality, 'size': size, 'date': date}
    for unit in UNITS:
        count = body.get(unit, 0)
        if type(count) is not int or not 0 <= count <= 10_000_000:
            raise AppError(400, 'Use quantidades inteiras, positivas ou zero, até 10 milhões.')
        result[unit] = count
    if not any(result[u] for u in UNITS):
        raise AppError(400, 'Informe ao menos uma embalagem.')
    if kind == 'exits' and sum(result[u] > 0 for u in UNITS) != 1:
        raise AppError(400, 'Registre uma embalagem por saída.')
    result['notes'] = text(body.get('notes', ''), 'Observações', 1000)
    if kind == 'entries':
        for field, label, limit in [('driver','Motorista',100),('truck','Placa',20),('destination','Câmara',80)]:
            result[field] = text(body.get(field, ''), label, limit)
        for field in ('gross', 'tare'):
            try:
                if isinstance(body.get(field, 0), bool): raise InvalidOperation()
                value = Decimal(str(body.get(field, 0)))
                if not value.is_finite() or not 0 <= value <= 1_000_000_000 or value != value.quantize(Decimal('.01')): raise InvalidOperation()
                result[field] = value
            except (InvalidOperation, ValueError):
                raise AppError(400, 'Informe pesos válidos, com até duas casas decimais.')
        if result['tare'] > result['gross']:
            raise AppError(400, 'A tara não pode ser maior que o peso bruto.')
    elif body.get('weightKg') not in (None, ''):
        # Campo opcional: saídas antigas não passam a ter peso zero inventado.
        try:
            if isinstance(body['weightKg'], bool): raise InvalidOperation()
            value = Decimal(str(body['weightKg']))
            if not value.is_finite() or not 0 < value <= 1_000_000_000 or value != value.quantize(Decimal('.01')): raise InvalidOperation()
            result['weightKg'] = value
        except (InvalidOperation, ValueError):
            raise AppError(400, 'Informe um peso de saída maior que zero, com até duas casas decimais, ou deixe em branco.')
    return result

def fingerprint(record, kind):
    return hashlib.sha256(json.dumps({'record': record, 'kind': kind}, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()

def require_role(user, allowed=ROLES):
    if not user or not user.get('active'):
        raise AppError(403, 'Acesso não autorizado ou pausado. Procure o administrador.')
    if user.get('role') not in allowed:
        raise AppError(403, 'Seu perfil não permite esta ação.')

def public_user(user):
    return {key:user.get(key) for key in ('id','name','username','email','role','active','created')}
