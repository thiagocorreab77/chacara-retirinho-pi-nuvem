const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');
const context = vm.createContext({ window: {} });
vm.runInContext(readFileSync(join(__dirname, '..', 'web', 'inventory.js'), 'utf8'), context);
const inv = context.window.RetirinhoInventory;
const record = (values = {}) => ({ quality: 'Ágata 00 importada', size: '2', destination: 'Câmara 1', caixotes: 0, sacos: 0, meiao: 0, bags: 0, ...values });
const sample = () => ({ entries: [record({ caixotes: 20, sacos: 30, meiao: 10, bags: 4 }), record({ caixotes: 8, destination: 'Câmara 2' }), record({ quality: 'Asterix', caixotes: 50 }), record({ size: '3', caixotes: 12 })], exits: [record({ caixotes: 6 }), record({ sacos: 5, meiao: 2, bags: 1 })] });
const filter = { quality: 'Ágata 00 importada', size: '2' };
const plain = value => JSON.parse(JSON.stringify(value));
test('estoque por qualidade e tamanho, com quatro embalagens independentes', () => {
  assert.deepEqual(plain(inv.balance(sample(), filter)), { caixotes: 22, sacos: 25, meiao: 8, bags: 3 });
  assert.equal(inv.balance(sample(), { quality: 'Asterix' }).caixotes, 50);
  assert.equal(inv.balance(sample(), { quality: 'Libra' }).caixotes, 0);
  assert.equal(inv.balance(sample()).caixotes, 84);
});
test('esgotar uma embalagem mantém o saldo das outras e não mistura tamanhos', () => {
  const data = sample();
  data.exits.push(record(inv.quantities('sacos', 25)));
  assert.equal(inv.balance(data, filter).sacos, 0);
  assert.equal(inv.balance(data, filter).caixotes, 22);
  assert.equal(inv.balance(data, { ...filter, size: '3' }).caixotes, 12);
});
test('saída em cada embalagem desconta apenas a quantidade da unidade escolhida', () => {
  for (const unit of Object.keys(inv.UNITS)) {
    const data = sample(); const before = inv.balance(data, filter);
    data.exits.push(record(inv.quantities(unit, 2)));
    const after = inv.balance(data, filter);
    for (const other of Object.keys(inv.UNITS)) assert.equal(after[other], before[other] - (other === unit ? 2 : 0));
  }
});
test('nomes com acentos, espaços e tamanhos numéricos mantêm o mesmo saldo', () => {
  assert.equal(inv.balance(sample(), { quality: '  agata  00 IMPORTADA ', size: 2 }).caixotes, 22);
});
test('quantidades inválidas são rejeitadas e não há conversão de embalagens', () => {
  for (const quantity of [0, -1, 1.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) assert.throws(() => inv.quantities('sacos', quantity));
  assert.throws(() => inv.quantities('kg', 1));
  assert.equal(inv.validCounts({ caixotes: 10, sacos: -1 }), false);
  assert.equal(inv.validCounts({ caixotes: 10, sacos: 'inválido' }), false);
  assert.equal(inv.validCounts({ caixotes: 10 }), true);
});
test('registros antigos com apenas caixotes continuam válidos sem mudar os dados', () => {
  const data = { entries: [record({ caixotes: 20, sacos: 10 })], exits: [{ quality: filter.quality, size: '2', caixotes: 6 }] };
  const before = JSON.stringify(data);
  assert.deepEqual(plain(inv.balance(data, filter)), { caixotes: 14, sacos: 10, meiao: 0, bags: 0 });
  assert.equal(inv.validCounts(data.exits[0]), true);
  assert.equal(JSON.stringify(data), before);
});
test('exclusão de entrada protege todas as embalagens já retiradas', () => {
  for (const unit of Object.keys(inv.UNITS)) {
    const data = { entries: [record({ [unit]: 10 })], exits: [record({ [unit]: 3 })] };
    assert.equal(inv.canRemoveEntry(data, data.entries[0]), false);
    data.exits = [];
    assert.equal(inv.canRemoveEntry(data, data.entries[0]), true);
  }
});
test('busca por texto e câmara não alteram o estoque real de todas as câmaras', () => {
  const data = sample();
  assert.deepEqual(plain(inv.balance(data, { ...filter, query: 'motorista inexistente', destination: 'Câmara 2' })), plain(inv.balance(data, filter)));
});

test('período inclui o dia inteiro nas duas pontas sem conversão de fuso', () => {
  const f = { startDate: '2026-11-02', endDate: '2026-11-03' };
  for (const date of ['2026-11-02', '2026-11-02T00:00', '2026-11-03T23:59']) assert.equal(inv.matchesPeriod({date}, f), true);
  for (const date of ['2026-11-01T23:59', '2026-11-04T00:00']) assert.equal(inv.matchesPeriod({date}, f), false);
  assert.equal(inv.matchesPeriod({date:'2026-11-03'}, {startDate:'2026-11-03'}), true);
  assert.equal(inv.matchesPeriod({date:'2026-11-02'}, {endDate:'2026-11-02'}), true);
  assert.equal(inv.matchesPeriod({date:'2026-11-03'}, {startDate:'2026-11-04',endDate:'2026-11-02'}), false);
  assert.equal(inv.matchesPeriod({date:'2026-11-03'}, {}), true);
});
test('saldo em kg desconta saídas, respeita qualidade e tamanho e ignora período', () => {
  const data = { entries: [record({gross:11000,tare:1000}), record({quality:'Libra',gross:900})], exits: [record({weightKg:2200})] };
  assert.deepEqual(plain(inv.weightBalance(data, {...filter,startDate:'2099-01-01',destination:'inexistente',query:'inexistente'})), {kg:7800,missing:0});
  assert.deepEqual(plain(inv.balance(sample(), {...filter,startDate:'2099-01-01',endDate:'2099-02-01'})), plain(inv.balance(sample(), filter)));
  data.exits = [];
  assert.equal(inv.weightBalance(data,filter).kg,10000);
});
test('peso ausente em dados antigos produz saldo parcial sem alterar o histórico', () => {
  const data = {entries:[record({gross:100,tare:0}),record({gross:0,tare:0})],exits:[record({caixotes:5}),record({weightKg:20})]};
  const before=JSON.stringify(data);
  assert.deepEqual(plain(inv.weightBalance(data)),{kg:80,missing:2});
  assert.equal(inv.weight(data.exits[0], false),null);
  assert.equal(JSON.stringify(data),before);
  assert.deepEqual(plain(inv.weightBalance({entries:[],exits:[]})),{kg:0,missing:0});
});
test('pesos usam centésimos de kg sem resíduos de ponto flutuante', () => {
  assert.equal(inv.weightBalance({entries:[record({gross:1.10,tare:0.30})],exits:[record({weightKg:0.70})]}).kg,0.10);
  assert.equal(inv.weightBalance({entries:[],exits:[record({weightKg:5})]}).kg,-5);
});
