from decimal import Decimal

from django.test import SimpleTestCase

from restaurante.services.pix import (
    PixError,
    build_payload,
    crc16_ccitt,
    detect_key_type,
    normalize_key,
    qr_svg,
)


def parse_emv(payload):
    """Decodifica o BR Code em {id: valor} (nível superior)."""
    fields, pos = {}, 0
    while pos < len(payload):
        field_id, size = payload[pos:pos + 2], int(payload[pos + 2:pos + 4])
        fields[field_id] = payload[pos + 4:pos + 4 + size]
        pos += 4 + size
    return fields


class CrcTests(SimpleTestCase):
    def test_exemplo_oficial_do_banco_central(self):
        payload = (
            '00020126580014br.gov.bcb.pix0136123e4567-e12b-12d1-a456-426655440000'
            '5204000053039865802BR5913Fulano de Tal6008BRASILIA62070503***6304'
        )
        self.assertEqual(crc16_ccitt(payload), '1D3D')


class KeyTests(SimpleTestCase):
    def test_detecta_tipos(self):
        self.assertEqual(detect_key_type('529.982.247-25'), 'cpf')
        self.assertEqual(detect_key_type('11.222.333/0001-81'), 'cnpj')
        self.assertEqual(detect_key_type('+55 (11) 98765-4321'), 'telefone')
        self.assertEqual(detect_key_type('(11) 98765-4321'), 'telefone')
        self.assertEqual(detect_key_type('Loja@Exemplo.com'), 'email')
        self.assertEqual(detect_key_type('123e4567-e12b-12d1-a456-426655440000'), 'aleatoria')

    def test_normaliza(self):
        self.assertEqual(normalize_key('529.982.247-25'), '52998224725')
        self.assertEqual(normalize_key('(11) 98765-4321', 'telefone'), '+5511987654321')
        self.assertEqual(normalize_key('Loja@Exemplo.com'), 'loja@exemplo.com')

    def test_cpf_invalido(self):
        with self.assertRaises(PixError):
            normalize_key('111.111.111-11', 'cpf')


class PayloadTests(SimpleTestCase):
    def build(self, **kwargs):
        params = dict(key='52998224725', name='Billá Burger', city='São Paulo', amount='25.9', txid='PEDIDO-52')
        params.update(kwargs)
        return build_payload(**params)

    def test_campos_obrigatorios_e_valor(self):
        fields = parse_emv(self.build())
        self.assertEqual(fields['00'], '01')
        self.assertEqual(fields['52'], '0000')
        self.assertEqual(fields['53'], '986')
        self.assertEqual(fields['54'], '25.90')
        self.assertEqual(fields['58'], 'BR')
        self.assertEqual(fields['59'], 'BILLA BURGER')
        self.assertEqual(fields['60'], 'SAO PAULO')
        account = parse_emv(fields['26'])
        self.assertEqual(account['00'], 'br.gov.bcb.pix')
        self.assertEqual(account['01'], '52998224725')
        self.assertEqual(parse_emv(fields['62'])['05'], 'PEDIDO52')

    def test_crc_confere(self):
        payload = self.build()
        self.assertEqual(crc16_ccitt(payload[:-4]), payload[-4:])

    def test_arredonda_valor(self):
        self.assertEqual(parse_emv(self.build(amount=Decimal('10.005')))['54'], '10.01')

    def test_sem_valor(self):
        self.assertNotIn('54', parse_emv(self.build(amount=None)))

    def test_limites_de_tamanho(self):
        fields = parse_emv(self.build(name='Restaurante Com Um Nome Muito Comprido Ltda', city='Santa Rita do Passa Quatro'))
        self.assertLessEqual(len(fields['59']), 25)
        self.assertLessEqual(len(fields['60']), 15)

    def test_valor_zero_falha(self):
        with self.assertRaises(PixError):
            self.build(amount='0')

    def test_qr_svg(self):
        self.assertTrue(qr_svg(self.build()).startswith('<svg'))
