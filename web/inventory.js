(() => {
  'use strict';
  const UNITS = Object.freeze({ caixotes: 'caixotes', sacos: 'sacos', meiao: 'sacos meião', bags: 'bags' });
  const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim().replace(/\s+/g, ' ').toLowerCase();
  const count = (record, unit) => Number(record[unit] ?? 0);
  const matches = (record, filter = {}) =>
    (!filter.quality || normalize(record.quality) === normalize(filter.quality)) &&
    (!filter.size || String(record.size) === String(filter.size));
  // Datas dos lançamentos são locais; não converter para UTC antes de filtrar.
  const validPeriod = ({ startDate, endDate } = {}) => !startDate || !endDate || startDate <= endDate;
  const matchesPeriod = (record, filter = {}) => {
    const day = String(record.date || '').slice(0, 10);
    return validPeriod(filter) && (!filter.startDate || day >= filter.startDate) && (!filter.endDate || day <= filter.endDate);
  };
  const weight = (record, isEntry) => {
    const value = isEntry ? Math.round(Number(record.gross || 0) * 100) - Math.round(Number(record.tare || 0) * 100)
      : Math.round(Number(record.weightKg) * 100);
    return Number.isFinite(value) && value > 0 ? value / 100 : null;
  };
  const weightTotals = (records, isEntry) => records.reduce((total, record) => {
    const kg = weight(record, isEntry);
    if (kg === null) total.missing++;
    else total.kg = (Math.round(total.kg * 100) + Math.round(kg * 100)) / 100;
    return total;
  }, { kg: 0, missing: 0 });
  const weightBalance = (data, filter = {}) => {
    const incoming = weightTotals(data.entries.filter(record => matches(record, filter)), true);
    const outgoing = weightTotals(data.exits.filter(record => matches(record, filter)), false);
    return { kg: (Math.round(incoming.kg * 100) - Math.round(outgoing.kg * 100)) / 100, missing: incoming.missing + outgoing.missing };
  };
  const totals = records => Object.fromEntries(Object.keys(UNITS).map(unit => [unit, records.reduce((total, record) => total + count(record, unit), 0)]));
  const balance = (data, filter = {}) => {
    const incoming = totals(data.entries.filter(record => matches(record, filter)));
    const outgoing = totals(data.exits.filter(record => matches(record, filter)));
    return Object.fromEntries(Object.keys(UNITS).map(unit => [unit, incoming[unit] - outgoing[unit]]));
  };
  const validCounts = record => Object.keys(UNITS).every(unit => Number.isSafeInteger(count(record, unit)) && count(record, unit) >= 0);
  const quantities = (unit, quantity) => {
    if (!Object.hasOwn(UNITS, unit) || !Number.isSafeInteger(quantity) || quantity < 1) throw new Error('Informe uma embalagem e uma quantidade inteira a partir de 1.');
    return Object.fromEntries(Object.keys(UNITS).map(key => [key, key === unit ? quantity : 0]));
  };
  const canRemoveEntry = (data, record) => {
    const filter = { quality: record.quality, size: record.size };
    const total = balance(data, filter);
    return Object.keys(UNITS).every(unit => total[unit] >= count(record, unit));
  };
  window.RetirinhoInventory = Object.freeze({ UNITS, normalize, count, matches, validPeriod, matchesPeriod, weight, weightTotals, weightBalance, totals, balance, validCounts, quantities, canRemoveEntry });
})();
