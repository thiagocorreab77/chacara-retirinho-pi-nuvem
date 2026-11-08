(async () => {
  'use strict';

  const access = window.RetirinhoAccess;
  const inventory = window.RetirinhoInventory;
  const UNITS = inventory.UNITS;
  const ROLE_LABELS = { admin: 'Administrador', operator: 'Operador', viewer: 'Visualizador' };
  let currentView = 'overview';
  const QUALITIES = [
    'Ágata 00 importada', 'Ágata F1 importada', 'Orkestra 00 importada',
    'Orkestra F1 importada', 'Asterix', 'Potia', 'Libra'
  ];
  const OTHER = '__outra';
  const currentUser = () => { try { return access.currentUser(); } catch { return null; } };
  const canManage = () => currentUser()?.role === 'admin';
  const canRegister = () => ['admin', 'operator'].includes(currentUser()?.role);
  const $ = id => document.getElementById(id);
  const fmt = value => new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 }).format(value);
  const unitName = (unit, quantity) => quantity === 1 ? ({ caixotes: 'caixote', sacos: 'saco', meiao: 'saco meião', bags: 'bag' })[unit] : UNITS[unit];
  const num = value => Number(value || 0);
  const norm = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim().replace(/\s+/g, ' ').toLowerCase();
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
  const net = record => inventory.weight(record, true) ?? 0;
  const author = record => record.registeredBy?.trim() || 'Não informado';
  const sum = (records, key) => records.reduce((total, record) => total + num(record[key]), 0);
  let data = { entries: [], exits: [] };
  let signedIn = false;
  let dataReadable = true;
  let toastTimer;
  let pendingDeletion = null;
  let syncTask = null, mutating = false, serviceStatus = null;
  const pendingSaves = new Map();
  let auditItems = [], auditCursor = null, auditBusy = false;

  function message(id, text = '') {
    $(id).textContent = text;
    $(id).hidden = !text;
  }

  function notify(text) {
    clearTimeout(toastTimer);
    message('toast', text);
    toastTimer = setTimeout(() => message('toast'), 5000);
  }

  function localDate(offsetDays = 0) {
    const date = new Date();
    date.setDate(date.getDate() + offsetDays);
    date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
    return date.toISOString().slice(0, 16);
  }

  function setEntryDate() { $('date').value = localDate(); }
  function setExitDate() { $('outDate').value = localDate().slice(0, 10); }
  function dateTimeFmt(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'Data inválida' : date.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
  }
  function dateFmt(value) { return String(value).split('-').reverse().join('/'); }
  function id() { return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`; }

  function validRecord(record, isEntry) {
    if (!record || typeof record.id !== 'string' || typeof record.quality !== 'string' || !record.quality.trim()) return false;
    if (!['1', '2', '3'].includes(String(record.size)) || typeof record.date !== 'string' || Number.isNaN(Date.parse(record.date))) return false;
    if (!inventory.validCounts(record)) return false;
    return !isEntry || ['gross', 'tare'].every(key => Number.isFinite(num(record[key])) && num(record[key]) >= 0);
  }

  function handleError(error, target = 'storageError') {
    if (error.status === 401 || !currentUser()) {
      access.forget(); data = {entries:[],exits:[]}; serviceStatus = null;
      showSession(false); message('loginError', error.message); return;
    }
    message(target, error.message || 'Não foi possível conectar. Confira sua internet e tente novamente.');
  }
  async function load() {
    if (syncTask) return syncTask;
    syncTask = (async () => {
      $('refreshData').disabled = true;
      try {
        await access.refreshUser();
        data = await access.loadRecords();
        dataReadable = true;
        message('storageError');
        $('syncStatus').textContent = (access.preview ? 'Prévia local atualizada às ' : 'Atualizado às ') + new Date().toLocaleTimeString('pt-BR') + '. Atualização automática a cada 45 segundos.';
        if (canManage()) await access.refreshUsers();
        render();
      } catch (error) {
        dataReadable = false;
        $('syncStatus').textContent = 'Sem atualização. Os dados exibidos podem estar desatualizados.';
        handleError(error); render();
      } finally { $('refreshData').disabled = false; syncTask = null; }
    })();
    return syncTask;
  }
  async function saveRecord(kind, record, form, errorId) {
    if (mutating) return;
    // Repetir o envio depois de uma falha de rede usa o mesmo ID e não duplica o registro.
    const payload = JSON.stringify({...record,id:undefined,created:undefined});
    const pending = pendingSaves.get(kind);
    record.id = pending?.payload === payload ? pending.id : id();
    pendingSaves.set(kind,{payload,id:record.id});
    mutating = true;
    const buttons = [...form.querySelectorAll('button')];
    buttons.forEach(button => {button.disabled=true;});
    try {
      await access.request('/'+kind,{method:'POST',body:JSON.stringify(record)});
      pendingSaves.delete(kind); form.reset();
      notify(access.preview ? 'Movimentação salva na prévia local.' : 'Movimentação salva no banco compartilhado.');
      if (syncTask) await syncTask;
      await load();
    } catch (error) {
      handleError(error,errorId);
      if (error.status === 409) await load();
    } finally { mutating=false; buttons.forEach(button=>{button.disabled=false;}); }
  }

  function allQualities() {
    const result = [...QUALITIES];
    for (const record of [...data.entries, ...data.exits]) {
      if (!result.some(quality => norm(quality) === norm(record.quality))) result.push(record.quality);
    }
    return result;
  }

  function refreshQualityOptions() {
    const options = allQualities().map(quality => `<option value="${esc(quality)}">${esc(quality)}</option>`).join('');
    for (const name of ['quality', 'outQuality', 'filterQuality']) {
      const previous = $(name).value;
      const markup = name === 'filterQuality'
        ? '<option value="">Todas as qualidades</option>' + options
        : options + `<option value="${OTHER}">Outra (informar o tipo)</option>`;
      // Não reconstruir o seletor durante atualizações se as opções forem iguais.
      if ($(name).dataset.options !== markup) {
        $(name).innerHTML = markup; $(name).dataset.options = markup;
        if ([...$(name).options].some(option => option.value === previous)) $(name).value = previous;
      }
      toggleOther(name);
    }
  }

  function toggleOther(name) {
    if (name === 'filterQuality') return;
    const wrap = name === 'quality' ? 'otherWrap' : 'outOtherWrap';
    const input = name === 'quality' ? 'qualityOther' : 'outQualityOther';
    $(wrap).hidden = $(name).value !== OTHER;
    $(input).required = $(name).value === OTHER;
    $(input).disabled = $(name).value !== OTHER;
  }

  function readQuality(name, other) {
    const entered = ($(name).value === OTHER ? $(other).value : $(name).value).trim().replace(/\s+/g, ' ');
    return allQualities().find(quality => norm(quality) === norm(entered)) || entered;
  }

  function filters() { return { query: norm($('search').value), quality: $('filterQuality').value, size: $('filterSize').value, destination: $('filterDest').value, startDate: $('filterStart').value, endDate: $('filterEnd').value }; }
  function filtered(isEntry) {
    const filter = filters();
    return (isEntry ? data.entries : data.exits).filter(record => {
      if (!inventory.matches(record, filter) || !inventory.matchesPeriod(record, filter)) return false;
      if (isEntry && filter.destination && record.destination !== filter.destination) return false;
      const text = [author(record), record.quality, `tamanho ${record.size}`, record.notes, ...Object.keys(UNITS).filter(unit => num(record[unit]) > 0).map(unit => UNITS[unit]), ...(isEntry ? [record.driver, record.truck, record.destination] : [])].join(' ');
      return !filter.query || norm(text).includes(filter.query);
    });
  }
  function quantityText(record) {
    return Object.keys(UNITS).filter(unit => num(record[unit]) > 0).map(unit => `${fmt(num(record[unit]))} ${unitName(unit, num(record[unit]))}`).join(' · ') || '0 embalagens';
  }
  function exitSelection() {
    return { quality: readQuality('outQuality', 'outQualityOther'), size: $('outSize').value };
  }
  function updateAvailableStock() {
    const filter = exitSelection(), unit = $('outUnit').value;
    const available = inventory.balance(data, filter)[unit];
    $('availableStock').textContent = !dataReadable ? 'Não foi possível consultar o estoque. Atualize os registros antes de continuar.'
      : filter.quality ? `Disponível: ${fmt(available)} ${unitName(unit, available)} de ${filter.quality}, tamanho ${filter.size}.`
      : 'Informe a qualidade para consultar o saldo disponível.';
  }

  function render() {
    refreshQualityOptions();
    const entries = filtered(true), exits = filtered(false), filter = filters();
    const periodValid = inventory.validPeriod(filter);
    message('filterError', periodValid ? '' : 'A data inicial não pode ser posterior à data final. Ajuste o período para consultar.');
    ['filterStart', 'filterEnd'].forEach(name => $(name).setAttribute('aria-invalid', String(!periodValid)));
    $('exportIn').disabled = $('exportOut').disabled = !periodValid;
    $('totalCaixotes').textContent = fmt(sum(entries, 'caixotes'));
    $('totalSacos').textContent = fmt(sum(entries, 'sacos'));
    $('totalMeiao').textContent = `${fmt(sum(entries, 'meiao'))} sacos meião`;
    const weightIn = inventory.weightTotals(entries, true), weightOut = inventory.weightTotals(exits, false);
    $('totalNet').textContent = `${fmt(weightIn.kg)} kg`;
    $('totalWeightOut').textContent = `Saídas no filtro: ${fmt(weightOut.kg)} kg`;
    $('periodWeightNote').textContent = weightIn.missing + weightOut.missing ? `${weightIn.missing + weightOut.missing} lançamento(s) sem peso. Totais parciais.` : 'Pesos dos registros filtrados.';
    $('totalOut').textContent = fmt(sum(exits, 'caixotes'));
    const outgoing = inventory.totals(exits);
    $('totalOutOther').textContent = ['sacos', 'meiao', 'bags'].map(unit => `${fmt(outgoing[unit])} ${unitName(unit, outgoing[unit])}`).join(' · ');
    const balance = inventory.balance(data, filter);
    const stockValue = unit => dataReadable ? fmt(balance[unit]) : 'Indisponível';
    $('currentStock').textContent = stockValue('caixotes');
    $('currentStockOther').innerHTML = ['sacos', 'meiao', 'bags'].map(unit => `<span><strong>${stockValue(unit)}</strong> ${unitName(unit, balance[unit])}</span>`).join('');
    const weightStock = inventory.weightBalance(data, filter);
    $('stockWeightLabel').textContent = weightStock.missing ? 'Saldo parcial em kg' : 'Estoque em kg';
    $('currentWeight').textContent = dataReadable ? `${fmt(weightStock.kg)} kg` : 'Indisponível';
    $('stockWeightNote').textContent = !dataReadable ? 'Atualize os registros para consultar.' : [weightStock.missing ? `${weightStock.missing} lançamento(s) sem peso informado.` : 'Peso recebido menos peso retirado.', weightStock.kg < 0 ? 'Revise as pesagens: as saídas informadas superam as entradas.' : ''].filter(Boolean).join(' ');
    $('stockWeightNote').dataset.warning = String(weightStock.missing > 0 || weightStock.kg < 0);
    $('stockScope').textContent = [filter.quality || 'Todas as qualidades', filter.size ? `Tamanho ${filter.size}` : 'Todos os tamanhos', 'Todas as câmaras', 'Todas as datas'].join(' · ');
    $('inCount').textContent = `${entries.length} registro(s) exibido(s)`;
    $('outCount').textContent = `${exits.length} registro(s) exibido(s)`;
    $('inEmpty').hidden = entries.length > 0;
    $('outEmpty').hidden = exits.length > 0;
    const sorted = records => records.slice().sort((a, b) => b.date.localeCompare(a.date) || num(b.created) - num(a.created));
    $('inBody').innerHTML = sorted(entries).map(record => `<tr>
      <td><strong>${esc(dateTimeFmt(record.date))}</strong></td>
      <td>${esc(author(record))}</td>
      <td><strong>${esc(record.truck || 'Sem placa')}</strong><div class="muted">${esc(record.driver || 'Motorista não informado')}</div></td>
      <td><strong>${esc(record.quality)}</strong><div class="muted"><span class="pill">Tamanho ${esc(record.size)}</span></div></td>
      <td><strong>${fmt(num(record.caixotes))} caixote(s)</strong><div class="muted">${fmt(num(record.sacos))} saco(s) · ${fmt(num(record.meiao))} meião${num(record.bags) ? ` · ${fmt(num(record.bags))} bag(s)` : ''}</div></td>
      <td><strong>${fmt(num(record.gross))} kg</strong><div class="muted">Tara: ${fmt(num(record.tare))} · Líquido: ${fmt(net(record))} kg</div></td>
      <td>${esc(record.destination || '—')}<div class="muted">${esc(record.notes || '')}</div></td>
      <td data-admin-only><button class="delete-button" type="button" data-del-in="${esc(record.id)}" aria-label="Excluir entrada de ${esc(record.quality)}, tamanho ${esc(record.size)}">Excluir</button></td>
    </tr>`).join('');
    $('outBody').innerHTML = sorted(exits).map(record => `<tr>
      <td><strong>${esc(dateFmt(record.date))}</strong></td><td>${esc(author(record))}</td><td><strong>${esc(record.quality)}</strong></td>
      <td><span class="pill">Tamanho ${esc(record.size)}</span></td><td><strong>${esc(quantityText(record))}</strong></td>
      <td>${inventory.weight(record, false) === null ? 'Não informado' : fmt(inventory.weight(record, false)) + ' kg'}</td>
      <td>${esc(record.notes || '—')}</td><td data-admin-only><button class="delete-button" type="button" data-del-out="${esc(record.id)}" aria-label="Excluir saída de ${esc(record.quality)}, tamanho ${esc(record.size)}">Excluir</button></td>
    </tr>`).join('');
    updateAvailableStock();
    applyPermissions();
    renderUsers();
    renderIntegrations();
  }

  function allowedViews() {
    return canManage() ? ['overview', 'register', 'users', 'integrations'] : canRegister() ? ['overview', 'register'] : ['overview'];
  }
  function switchView(view, focus = false) {
    const previousView = currentView;
    currentView = allowedViews().includes(view) ? view : 'overview';
    document.querySelectorAll('[data-tab]').forEach(button => {
      const selected = button.dataset.tab === currentView;
      button.setAttribute('aria-selected', String(selected));
      button.tabIndex = selected ? 0 : -1;
      $('view-' + button.dataset.tab).hidden = !selected;
    });
    if (focus) $('tab-' + currentView).focus();
    if (currentView === 'integrations' && previousView !== currentView) loadAudit();
  }
  function applyPermissions() {
    const user = currentUser();
    if (!canManage()) { auditItems = []; auditCursor = null; $('auditBody').innerHTML = ''; }
    document.querySelectorAll('[data-admin-only]').forEach(element => { element.hidden = !canManage(); });
    document.querySelectorAll('[data-register-only]').forEach(element => { element.hidden = !canRegister(); });
    $('accountName').textContent = user?.name || 'Usuário';
    document.querySelectorAll('[data-record-author]').forEach(element => { element.textContent = user?.name || 'Usuário'; });
    $('accountAvatar').textContent = (user?.name || 'U').slice(0, 1).toUpperCase();
    $('accountRole').textContent = ROLE_LABELS[user?.role] || 'Visualizador';
    switchView(currentView);
  }
  document.querySelectorAll('[data-tab]').forEach(button => {
    button.addEventListener('click', () => switchView(button.dataset.tab));
    button.addEventListener('keydown', event => {
      const views = allowedViews();
      let index = views.indexOf(currentView);
      if (event.key === 'ArrowRight') index = (index + 1) % views.length;
      else if (event.key === 'ArrowLeft') index = (index - 1 + views.length) % views.length;
      else if (event.key === 'Home') index = 0;
      else if (event.key === 'End') index = views.length - 1;
      else return;
      event.preventDefault(); switchView(views[index], true);
    });
  });
  document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => {
    switchView(button.dataset.view, true);
    window.scrollTo(0, 0);
  }));

  function showSession(active) {
    signedIn = Boolean(active && currentUser());
    $('loginScreen').hidden = signedIn;
    $('app').hidden = !signedIn;
    document.title = signedIn ? 'Controle de batatas | Chácara Retirinho' : 'Entrar | Chácara Retirinho';
    if (signedIn) { currentView = 'overview'; render(); $('dashboardTitle').focus({ preventScroll: true }); }
  }
  $('loginForm').addEventListener('submit', async event => {
    event.preventDefault();
    const submit = event.target.querySelector('[type=submit]');
    submit.disabled = true; message('loginError');
    try { await access.login(); }
    catch (error) { message('loginError',error.message); submit.disabled=false; }
  });
  $('logout').addEventListener('click', async () => {
    $('logout').disabled=true;
    await access.logout();
  });
  $('refreshData').addEventListener('click',load);

  $('quality').addEventListener('change', () => toggleOther('quality'));
  const refreshExit = () => { message('exitError'); updateAvailableStock(); };
  $('outQuality').addEventListener('change', () => { toggleOther('outQuality'); refreshExit(); });
  ['outSize', 'outUnit'].forEach(name => $(name).addEventListener('change', refreshExit));
  $('outQualityOther').addEventListener('input', refreshExit);
  $('outQuantity').addEventListener('input', () => message('exitError'));

  $('loadForm').addEventListener('submit', async event => {
    event.preventDefault();
    if (!signedIn || !canRegister()) return;
    message('entryError');
    const caixotes = num($('caixotes').value), sacos = num($('sacos').value), meiao = num($('meiao').value), bags = num($('bags').value);
    const gross = num($('gross').value), tare = num($('tare').value);
    if (![caixotes, sacos, meiao, bags].every(value => Number.isSafeInteger(value) && value >= 0) || caixotes + sacos + meiao + bags === 0) return message('entryError', 'Informe ao menos uma embalagem recebida, usando quantidades inteiras e positivas.');
    if (![gross, tare].every(value => Number.isFinite(value) && value >= 0) || tare > gross) return message('entryError', 'Confira os pesos: a tara não pode ser maior que o peso bruto, e os valores não podem ser negativos.');
    const quality = readQuality('quality', 'qualityOther');
    if (!quality) return message('entryError', 'Informe a qualidade ou o tipo da batata.');
    const record = { id: id(), created: Date.now(), date: $('date').value, caixotes, sacos, meiao, bags, gross, tare, quality, size: $('size').value, driver: $('driver').value.trim(), truck: $('truck').value.trim().toUpperCase(), destination: $('destination').value, notes: $('notes').value.trim() };
    if (!validRecord(record, true)) return message('entryError', 'Confira a data, o tamanho e as quantidades informadas.');
    await saveRecord('entries',record,event.target,'entryError');
  });
  $('outForm').addEventListener('submit', async event => {
    event.preventDefault();
    if (!signedIn || !canRegister()) return;
    message('exitError');
    const quantity = num($('outQuantity').value), unit = $('outUnit').value, filter = exitSelection();
    let counts;
    try { counts = inventory.quantities(unit, quantity); }
    catch (error) { return message('exitError', error.message); }
    if (!filter.quality) return message('exitError', 'Informe a espécie ou a qualidade retirada.');
    const available = inventory.balance(data, filter)[unit];
    if (quantity > available) return message('exitError', `Saída não registrada. Há ${fmt(available)} ${UNITS[unit]} disponíveis de ${filter.quality}, tamanho ${filter.size}. Confira a embalagem, a qualidade e o tamanho ou registre a entrada que falta.`);
    const record = { id: id(), created: Date.now(), date: $('outDate').value, ...counts, ...filter, notes: $('outNotes').value.trim() };
    if ($('outWeight').value !== '') {
      const weight = Number($('outWeight').value);
      if (!Number.isFinite(weight) || weight <= 0 || weight > 1000000000 || Math.abs(weight * 100 - Math.round(weight * 100)) > 0.00001) return message('exitError', 'Informe um peso maior que zero, com até duas casas decimais, ou deixe em branco.');
      record.weightKg = weight;
    }
    if (!validRecord(record, false)) return message('exitError', 'Confira a data, o tamanho e a quantidade da saída.');
    await saveRecord('exits',record,event.target,'exitError');
  });

  $('loadForm').addEventListener('reset', () => setTimeout(() => { toggleOther('quality'); setEntryDate(); message('entryError'); }, 0));
  $('outForm').addEventListener('reset', () => setTimeout(() => { toggleOther('outQuality'); setExitDate(); updateAvailableStock(); message('exitError'); }, 0));

  $('inBody').addEventListener('click', event => {
    if (!signedIn || !canManage()) return;
    const button = event.target.closest('[data-del-in]');
    if (!button) return;
    const record = data.entries.find(item => item.id === button.dataset.delIn);
    if (!record) return;
    if (!inventory.canRemoveEntry(data, record)) {
      notify('Esta entrada tem embalagens já retiradas. Confira primeiro as saídas dessa qualidade e tamanho.');
      return;
    }
    requestDeletion('entries', record);
  });
  $('outBody').addEventListener('click', event => {
    if (!signedIn || !canManage()) return;
    const button = event.target.closest('[data-del-out]');
    if (!button) return;
    const record = data.exits.find(item => item.id === button.dataset.delOut);
    if (record) requestDeletion('exits', record);
  });

  function requestDeletion(collection, record) {
    pendingDeletion = { collection, id: record.id };
    $('deleteDescription').textContent = `Excluir ${collection === 'entries' ? 'a entrada' : 'a saída'} de ${record.quality}, tamanho ${record.size}, com ${quantityText(record)}? O saldo será atualizado. Esta ação não pode ser desfeita.`;
    $('deleteDialog').showModal();
  }
  $('deleteDialog').addEventListener('close', () => { pendingDeletion = null; });
  $('confirmDelete').addEventListener('click', async () => {
    if (!pendingDeletion || !signedIn || !canManage()) return;
    const { collection, id: recordId } = pendingDeletion;
    const record = data[collection].find(item => item.id === recordId);
    if (!record) { $('deleteDialog').close(); return; }
    // Revalida: outra aba pode ter registrado uma retirada enquanto o diálogo estava aberto.
    if (collection === 'entries' && !inventory.canRemoveEntry(data, record)) {
      $('deleteDialog').close();
      notify('A exclusão deixaria o saldo negativo. Confira as saídas antes de excluir.');
      return;
    }
    if (mutating) return;
    mutating=true; $('confirmDelete').disabled=true;
    try {
      await access.request('/'+collection+'/'+encodeURIComponent(recordId),{method:'DELETE'});
      $('deleteDialog').close(); notify(access.preview ? 'Exemplo excluído e saldo local atualizado.' : 'Registro excluído e saldo atualizado.'); if (syncTask) await syncTask; await load();
    } catch (error) { $('deleteDialog').close(); handleError(error); }
    finally { mutating=false; $('confirmDelete').disabled=false; }

  });

  function clearFilters() {
    ['search', 'filterQuality', 'filterSize', 'filterDest', 'filterStart', 'filterEnd'].forEach(name => { $(name).value = ''; });
    render();
  }
  $('clearFilters').addEventListener('click', clearFilters);
  ['search', 'filterQuality', 'filterSize', 'filterDest', 'filterStart', 'filterEnd'].forEach(name => $(name).addEventListener(name === 'search' ? 'input' : 'change', render));

  function exportCsv(name, columns, records) {
    if (!signedIn || !canManage()) return;
    if (!records.length) { notify('Não há registros no filtro atual para exportar.'); return; }
    const quote = value => {
      let text = String(value ?? '');
      // Evita que texto fornecido por usuário seja interpretado como fórmula em planilhas.
      if (/^[\s]*[=+@-]/.test(text) || /^[\t\r\n]/.test(text)) text = "'" + text;
      return '"' + text.replace(/"/g, '""') + '"';
    };
    const csv = '\uFEFF' + [columns.map(column => quote(column[0])).join(';'), ...records.map(record => columns.map(column => quote(column[1](record))).join(';'))].join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
    const link = document.createElement('a');
    link.href = url; link.download = name;
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    notify('Exportação CSV preparada. Confira os downloads do navegador.');
  }
  $('exportIn').addEventListener('click', () => exportCsv('entradas_batata.csv', [
    ['Data e hora', record => record.date], ['Registrado por', author], ['Qualidade', record => record.quality], ['Tamanho', record => record.size], ['Caixotes', record => record.caixotes], ['Sacos', record => record.sacos], ['Sacos meião', record => record.meiao], ['Bags', record => record.bags], ['Motorista', record => record.driver], ['Placa', record => record.truck], ['Peso bruto kg', record => record.gross], ['Tara kg', record => record.tare], ['Peso líquido kg', record => net(record)], ['Câmara fria', record => record.destination], ['Observações', record => record.notes]
  ], filtered(true)));
  $('exportOut').addEventListener('click', () => exportCsv('saidas_batata.csv', [
    ['Data', record => record.date], ['Registrado por', author], ['Peso líquido kg', record => inventory.weight(record, false) ?? ''], ['Espécie / qualidade', record => record.quality], ['Tamanho', record => record.size], ['Caixotes', record => num(record.caixotes)], ['Sacos', record => num(record.sacos)], ['Sacos meião', record => num(record.meiao)], ['Bags', record => num(record.bags)], ['Observações', record => record.notes]
  ], filtered(false)));

  function renderUsers() {
    if (!canManage()) { $('usersBody').innerHTML = ''; return; }
    const records = access.listUsers();
    const self = currentUser()?.id;
    $('usersBody').innerHTML = records.map(user => `<tr>
      <td><strong>${esc(user.name)}${user.id === self ? ' (você)' : ''}</strong><div class="muted">${esc(user.email)}</div></td>
      <td><select data-user-role="${esc(user.id)}" aria-label="Perfil de ${esc(user.email)}" ${user.id === self ? 'disabled' : ''}>${Object.entries(ROLE_LABELS).map(([role, label]) => `<option value="${role}" ${role === user.role ? 'selected' : ''}>${label}</option>`).join('')}</select></td>
      <td><span class="status-tag ${user.active ? '' : 'pending'}">${user.active ? 'Ativo' : 'Pausado'}</span></td>
      <td><button class="secondary" type="button" data-user-toggle="${esc(user.id)}" ${user.id === self ? 'disabled' : ''} aria-label="${user.active ? 'Pausar' : 'Reativar'} acesso de ${esc(user.email)}">${user.id === self ? 'Seu acesso' : user.active ? 'Pausar' : 'Reativar'}</button></td>
    </tr>`).join('');
    $('usersCount').textContent = `${records.length} login(s) · ${records.filter(user => user.active).length} ativo(s)`;
  }
  $('userForm').addEventListener('submit', async event => {
    event.preventDefault();
    if (!canManage()) return;
    message('userError'); $('createUser').disabled = true;
    try {
      await access.createUser({ name: $('newName').value, email: $('newEmail').value, role: $('newRole').value });
      event.target.reset(); await access.refreshUsers(); renderUsers(); renderIntegrations(); notify(access.preview ? 'Acesso fictício criado; nenhum e-mail enviado.' : 'Convite enviado por e-mail.');
    } catch (error) { message('userError', error.message); }
    finally { $('createUser').disabled = false; }
  });
  $('usersBody').addEventListener('change', async event => {
    const select = event.target.closest('[data-user-role]');
    if (!select) return;
    try { select.disabled=true; await access.setRole(select.dataset.userRole, select.value); await access.refreshUsers(); notify('Perfil de acesso atualizado.'); }
    catch (error) { notify(error.message); }
    renderUsers();
  });
  $('usersBody').addEventListener('click', async event => {
    const button = event.target.closest('[data-user-toggle]');
    if (!button || !canManage()) return;
    try {
      const user = access.listUsers().find(record => record.id === button.dataset.userToggle);
      if (user) { button.disabled=true; await access.setActive(user.id, !user.active); await access.refreshUsers(); notify(user.active ? 'Acesso pausado.' : 'Acesso reativado.'); }
    } catch (error) { notify(error.message); }
    renderUsers(); renderIntegrations();
  });

  function renderIntegrations() {
    if (!canManage()) return;
    $('databaseStatus').textContent = serviceStatus?.database === 'demo' ? 'Simulado' : serviceStatus?.database === 'connected' ? 'Conectado' : 'A verificar';
    $('apiStatus').textContent = serviceStatus?.api === 'demo' ? 'Simulada' : serviceStatus?.api === 'connected' ? 'Conectada' : 'A verificar';
    $('databaseSummary').textContent = `${data.entries.length} entrada(s) e ${data.exits.length} saída(s) no histórico`;
    $('usersSummary').textContent = `${access.listUsers().filter(u=>u.active).length} acesso(s) ativo(s)`;
    $('serviceCheckedAt').textContent = serviceStatus ? 'Verificado em '+dateTimeFmt(serviceStatus.checkedAt) : 'Nenhuma verificação concluída';
  }
  async function checkServices() {
    if (!canManage()) return;
    $('checkIntegrations').disabled=true; message('integrationError');
    try { serviceStatus=await access.request('/status'); }
    catch (error) { serviceStatus=null; handleError(error,'integrationError'); }
    finally { renderIntegrations(); $('checkIntegrations').disabled=false; }
  }
  $('checkIntegrations').addEventListener('click',checkServices);
  const AUDIT_LABELS = {'entries.created':'Entrada registrada','exits.created':'Saída registrada','entries.deleted':'Entrada excluída','exits.deleted':'Saída excluída','user.updated':'Acesso alterado','user.invited':'Usuário convidado','session.observed':'Sessão autenticada observada'};
  function renderAudit() {
    if (!canManage()) return;
    const search=norm($('auditSearch').value), type=$('auditType').value;
    const records=auditItems.filter(item=>(!type || (type==='movement' ? /^(entries|exits)\./.test(item.action) : item.action.startsWith(type))) && (!search || norm([item.actorName,AUDIT_LABELS[item.action]||item.action,item.target,JSON.stringify(item.details)].join(' ')).includes(search)));
    $('auditBody').innerHTML=records.map(item=>`<tr><td>${esc(dateTimeFmt(item.at))}</td><td><strong>${esc(item.actorName)}</strong><span class="muted">${esc(ROLE_LABELS[item.actorRole] || item.actorRole)}</span></td><td>${esc(AUDIT_LABELS[item.action]||item.action)}</td><td><span class="audit-target">${esc(item.target)}</span><details><summary>Ver detalhes</summary><pre>${esc(JSON.stringify(item.details,null,2))}</pre></details></td></tr>`).join('');
    $('auditEmpty').hidden=records.length>0;
    $('auditCount').textContent=`${records.length} evento(s) exibido(s) de ${auditItems.length} carregado(s)`;
    $('auditSummary').textContent=`Nos eventos carregados: ${auditItems.filter(item=>item.action==='session.observed').length} sessão(ões), ${new Set(auditItems.map(item=>item.actorId)).size} pessoa(s) e ${auditItems.filter(item=>/^(entries|exits)\./.test(item.action)).length} movimentação(ões).${auditCursor ? ' Existem eventos mais antigos para carregar.' : ''}`;
    $('moreAudit').hidden=!auditCursor;
  }
  async function loadAudit(append=false) {
    if (!canManage() || auditBusy) return;
    auditBusy=true; $('refreshAudit').disabled=true; $('moreAudit').disabled=true; message('auditError');
    try {
      const page=await access.request('/audit'+(append&&auditCursor?'?cursor='+encodeURIComponent(auditCursor):''));
      if (!canManage()) return;
      auditItems=append?[...new Map([...auditItems,...page.items].map(item=>[item.id,item])).values()]:page.items;
      auditCursor=page.cursor;renderAudit();
    } catch(error) {handleError(error,'auditError');}
    finally {auditBusy=false; $('refreshAudit').disabled=false; $('moreAudit').disabled=false;}
  }
  $('refreshAudit').addEventListener('click',()=>loadAudit());
  $('moreAudit').addEventListener('click',()=>loadAudit(true));
  $('auditSearch').addEventListener('input',renderAudit);
  $('auditType').addEventListener('change',renderAudit);


  const loginSubmit = $('loginForm').querySelector('[type=submit]');
  loginSubmit.disabled=true;
  refreshQualityOptions(); setEntryDate(); setExitDate();
  try {
    await access.initialize();
    showSession(Boolean(currentUser()));
    if (currentUser()) { await load(); await checkServices(); }
  } catch (error) { showSession(false); message('loginError',error.message); }
  finally { loginSubmit.disabled=false; }
  setInterval(() => {if (signedIn && !document.hidden && !mutating) load();},45000);
  document.addEventListener('visibilitychange',()=>{if (signedIn && !document.hidden && !mutating) load();});
})();
