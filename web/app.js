/**
 * HomeWorker Telegram Mini App — Клиентская логика приложения (Vanilla JS)
 * Поддерживает работу с живым сервером aiogram/aiohttp и автономный режим предпросмотра.
 */

(function () {
  'use strict';

  // Базовые предметы психологии (10 дисциплин)
  const DEFAULT_SUBJECTS = [
    { id: 1, name: 'Психология эмоций и мотивации' },
    { id: 2, name: 'Психология личности' },
    { id: 3, name: 'Психодиагностика' },
    { id: 4, name: 'Экспериментальная психология' },
    { id: 5, name: 'Статистика' },
    { id: 6, name: 'Методология' },
    { id: 7, name: 'Медицинская психология' },
    { id: 8, name: 'Социальная психология' },
    { id: 9, name: 'Основы управления интеллектуальной собственностью' },
    { id: 10, name: 'Основы психологической помощи' },
  ];

  // Демонстрационное расписание
  const DEFAULT_DAYS = [
    { day_of_week: 1, day_name: 'Понедельник', content: '1 пара: Психология личности (ауд. 302, лекция)\n2 пара: Статистика (ауд. 210, семинар)' },
    { day_of_week: 2, day_name: 'Вторник', content: '1 пара: Экспериментальная психология (лабораторная)\n2 пара: Психодиагностика (ауд. 405)' },
    { day_of_week: 3, day_name: 'Среда', content: '2 пара: Психология эмоций и мотивации (лекция)\n3 пара: Методология психологических исследований' },
    { day_of_week: 4, day_name: 'Четверг', content: '1 пара: Медицинская психология (ауд. 108)\n2 пара: Социальная психология (семинар)' },
    { day_of_week: 5, day_name: 'Пятница', content: '1 пара: Основы психологической помощи\n2 пара: Основы управления интеллектуальной собственностью' },
    { day_of_week: 6, day_name: 'Суббота', content: 'День самостоятельной работы / спецкурсы' },
  ];

  // Демонстрационные домашние задания
  const DEFAULT_HOMEWORK = [
    { id: 1, subject_id: 2, subject_name: 'Психология личности', due_date: 'К следующему Пн', task_text: 'Подготовить конспект по концепции самоактуализации А. Маслоу и теории черт личности Г. Олпорта.' },
    { id: 2, subject_id: 5, subject_name: 'Статистика', due_date: 'К 15 ноября', task_text: 'Решить практические задачи №4 и №7 на расчёт рангового коэффициента корреляции Спирмена.' },
    { id: 3, subject_id: 3, subject_name: 'Психодиагностика', due_date: 'К четвергу', task_text: 'Изучить стандартизацию методики MMPI, интерпретацию профилей и шкал валидности (L, F, K).' },
  ];

  // Демонстрационный пул докладов
  const DEFAULT_REPORTS = [
    {
      id: 1,
      subject_id: 2,
      subject_name: 'Психология личности',
      seminar_date: '18 декабря',
      is_published: 1,
      release_datetime_random: '12.12.2026, 14:35',
      topics: [
        { id: 101, topic_number: 1, topic_text: 'Пятифакторная модель личности («Большая пятёрка» / Big Five): структура и психометрическая валидность', is_taken: true, student_name: 'Анна Смирнова', is_mine: false },
        { id: 102, topic_number: 2, topic_text: 'Аналитическая психология К.Г. Юнга: структура психики и архетипы коллективного бессознательного', is_taken: false, student_name: null, is_mine: false },
        { id: 103, topic_number: 3, topic_text: 'Когнитивная теория личностных конструктов Джорджа Келли', is_taken: false, student_name: null, is_mine: false },
        { id: 104, topic_number: 4, topic_text: 'Динамическая концепция личности и теория поля Курта Левина', is_taken: false, student_name: null, is_mine: false },
      ],
    },
  ];

  // 1. Инициализация Telegram WebApp SDK
  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
    try {
      tg.setHeaderColor('#fbf5f2');
      tg.setBackgroundColor('#fbf5f2');
    } catch (e) {}
  }

  // 2. Внутреннее состояние приложения
  const state = {
    user: null,
    isAdmin: false,
    isOffline: false,
    currentWeekType: 'current',
    selectedHwSubject: 'all',
    selectedReportSubject: 'all',
    subjects: [...DEFAULT_SUBJECTS],
    demoHomework: [...DEFAULT_HOMEWORK],
    demoReports: JSON.parse(JSON.stringify(DEFAULT_REPORTS)),
    // Режим разработки для обычных браузеров
    devTelegramId: '111222', // По умолчанию обычный студент
    isTelegram: Boolean(tg && tg.initData && tg.initData.length > 0),
  };

  // DOM Элементы
  const elements = {
    toast: document.getElementById('toast'),
    userName: document.getElementById('userName'),
    userRole: document.getElementById('userRole'),
    userBadge: document.getElementById('userBadge'),
    devModeBar: document.getElementById('devModeBar'),
    devBtnStudent: document.getElementById('devBtnStudent'),
    devBtnAdmin: document.getElementById('devBtnAdmin'),
    offlineNotice: document.getElementById('offlineNotice'),
    navItemAdmin: document.getElementById('navItemAdmin'),
    adminScheduleBar: document.getElementById('adminScheduleBar'),
    btnWeekCurrent: document.getElementById('btnWeekCurrent'),
    btnWeekNext: document.getElementById('btnWeekNext'),
    scheduleDaysList: document.getElementById('scheduleDaysList'),
    hwSubjectsFilter: document.getElementById('hwSubjectsFilter'),
    homeworkList: document.getElementById('homeworkList'),
    reportSubjectsFilter: document.getElementById('reportSubjectsFilter'),
    reportsBatchesList: document.getElementById('reportsBatchesList'),
    // Модальные окна
    modalEditSchedule: document.getElementById('modalEditSchedule'),
    formEditSchedule: document.getElementById('formEditSchedule'),
    editScheduleTitle: document.getElementById('modalScheduleTitle'),
    editScheduleWeekType: document.getElementById('editScheduleWeekType'),
    editScheduleDayIdx: document.getElementById('editScheduleDayIdx'),
    editScheduleContent: document.getElementById('editScheduleContent'),
    modalHomework: document.getElementById('modalHomework'),
    formHomework: document.getElementById('formHomework'),
    modalHomeworkTitle: document.getElementById('modalHomeworkTitle'),
    editHwId: document.getElementById('editHwId'),
    hwSubjectSelect: document.getElementById('hwSubjectSelect'),
    btnToggleManualSubject: document.getElementById('btnToggleManualSubject'),
    hwManualSubjectWrap: document.getElementById('hwManualSubjectWrap'),
    hwManualSubjectInput: document.getElementById('hwManualSubjectInput'),
    hwDueDate: document.getElementById('hwDueDate'),
    hwTaskText: document.getElementById('hwTaskText'),
    modalReportBatch: document.getElementById('modalReportBatch'),
    formReportBatch: document.getElementById('formReportBatch'),
    reportSubjectSelect: document.getElementById('reportSubjectSelect'),
    reportSeminarDate: document.getElementById('reportSeminarDate'),
    reportReleaseDate: document.getElementById('reportReleaseDate'),
    reportTopicsText: document.getElementById('reportTopicsText'),
  };

  // Виброотклик Telegram (Haptic Feedback)
  function triggerHaptic(type = 'light') {
    if (!tg?.HapticFeedback) return;
    try {
      if (type === 'success' || type === 'error' || type === 'warning') {
        tg.HapticFeedback.notificationOccurred(type);
      } else {
        tg.HapticFeedback.impactOccurred(type);
      }
    } catch (e) {}
  }

  // Всплывающее уведомление (Toast)
  let toastTimer = null;
  function showToast(text, type = 'info') {
    if (!elements.toast) return;
    clearTimeout(toastTimer);
    elements.toast.textContent = text;
    elements.toast.className = `toast ${type}`;
    elements.toast.classList.remove('hidden');

    toastTimer = setTimeout(() => {
      elements.toast.classList.add('hidden');
    }, 3200);
  }

  // Диалог подтверждения
  async function confirmDialog(message) {
    if (tg?.showConfirm) {
      return new Promise((resolve) => {
        tg.showConfirm(message, (ok) => resolve(ok));
      });
    }
    return window.confirm(message);
  }

  // Клиент API с прозрачной поддержкой Telegram initData и fallback
  async function apiFetch(endpoint, options = {}) {
    const headers = {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    };

    if (state.isTelegram && tg?.initData) {
      headers['Authorization'] = `tma ${tg.initData}`;
    } else {
      headers['X-Dev-Telegram-Id'] = String(state.devTelegramId);
    }

    const resp = await fetch(endpoint, { ...options, headers });
    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      throw new Error(errData.error || `HTTP ${resp.status}`);
    }
    return await resp.json();
  }

  // ---------------- УПРАВЛЕНИЕ МОДАЛЬНЫМИ ОКНАМИ ---------------- //

  function openModal(modal) {
    if (typeof modal === 'string') modal = document.getElementById(modal);
    if (!modal) return;
    modal.classList.remove('hidden');
    triggerHaptic('light');
  }

  function closeModal(modal) {
    if (typeof modal === 'string') modal = document.getElementById(modal);
    if (!modal) return;
    modal.classList.add('hidden');
  }

  document.querySelectorAll('[data-close-modal]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-close-modal');
      closeModal(targetId);
    });
  });

  document.querySelectorAll('.modal-backdrop').forEach((backdrop) => {
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) {
        closeModal(backdrop);
      }
    });
  });

  // ---------------- НАВИГАЦИЯ И ВКЛАДКИ ---------------- //

  function setupTabs() {
    const navItems = document.querySelectorAll('.nav-item');
    const tabContents = document.querySelectorAll('.tab-content');

    navItems.forEach((btn) => {
      btn.addEventListener('click', () => {
        const targetTabId = btn.getAttribute('data-tab');
        triggerHaptic('light');

        navItems.forEach((b) => b.classList.remove('active'));
        tabContents.forEach((t) => t.classList.remove('active'));

        btn.classList.add('active');
        const activeTab = document.getElementById(targetTabId);
        if (activeTab) activeTab.classList.add('active');
      });
    });

    document.getElementById('btnDashGoSchedule')?.addEventListener('click', () => {
      document.querySelector('[data-tab="tabSchedule"]')?.click();
    });
    document.getElementById('btnDashCreateHw')?.addEventListener('click', () => {
      document.querySelector('[data-tab="tabHomework"]')?.click();
      document.getElementById('btnOpenAddHwModal')?.click();
    });
    document.getElementById('btnDashCreateReport')?.addEventListener('click', () => {
      document.querySelector('[data-tab="tabReports"]')?.click();
      document.getElementById('btnOpenAddReportModal')?.click();
    });
  }

  // ---------------- 1. МОДУЛЬ ПОЛЬЗОВАТЕЛЯ И АУТЕНТИФИКАЦИИ ---------------- //

  async function loadUser() {
    try {
      const data = await apiFetch('/api/me');
      state.user = data.user;
      state.isAdmin = Boolean(data.is_admin);
      state.isOffline = false;
      elements.offlineNotice?.classList.add('hidden');
    } catch (err) {
      // Автономный режим предпросмотра
      state.isOffline = true;
      elements.offlineNotice?.classList.remove('hidden');
      state.isAdmin = state.devTelegramId === '999888';
      state.user = {
        telegram_id: state.devTelegramId,
        username: state.isAdmin ? 'starosta' : 'student',
        full_name: state.isAdmin ? 'Елена (Староста)' : 'Алексей (Студент)',
      };
    }

    elements.userBadge?.classList.remove('skeleton');
    if (elements.userName) {
      elements.userName.textContent = state.user.full_name || `ID: ${state.user.telegram_id}`;
    }

    if (state.isAdmin) {
      if (elements.userRole) {
        elements.userRole.textContent = '👑 Староста';
        elements.userRole.classList.add('admin');
      }
      elements.navItemAdmin?.classList.remove('hidden');
      elements.adminScheduleBar?.classList.remove('hidden');
      document.querySelectorAll('.admin-only').forEach((el) => el.classList.remove('hidden'));
    } else {
      if (elements.userRole) {
        elements.userRole.textContent = 'Студент';
        elements.userRole.classList.remove('admin');
      }
      elements.navItemAdmin?.classList.add('hidden');
      elements.adminScheduleBar?.classList.add('hidden');
      document.querySelectorAll('.admin-only').forEach((el) => el.classList.add('hidden'));
    }
  }

  function setupDevModeSwitch() {
    if (!state.isTelegram) {
      elements.devModeBar?.classList.remove('hidden');

      elements.devBtnStudent?.addEventListener('click', async () => {
        state.devTelegramId = '111222';
        elements.devBtnStudent.classList.add('active');
        elements.devBtnAdmin.classList.remove('active');
        triggerHaptic('light');
        await reloadAll();
      });

      elements.devBtnAdmin?.addEventListener('click', async () => {
        state.devTelegramId = '999888';
        elements.devBtnAdmin.classList.add('active');
        elements.devBtnStudent.classList.remove('active');
        triggerHaptic('light');
        await reloadAll();
      });
    }
  }

  // ---------------- 2. МОДУЛЬ ПРЕДМЕТОВ ---------------- //

  async function loadSubjects() {
    try {
      const data = await apiFetch('/api/subjects');
      if (data.subjects && data.subjects.length > 0) {
        state.subjects = data.subjects;
      } else {
        state.subjects = [...DEFAULT_SUBJECTS];
      }
    } catch (err) {
      state.subjects = [...DEFAULT_SUBJECTS];
    }

    // Заполняем выпадающие списки модальных окон
    const hwSelect = elements.hwSubjectSelect;
    const reportSelect = elements.reportSubjectSelect;
    if (hwSelect) hwSelect.innerHTML = '';
    if (reportSelect) reportSelect.innerHTML = '';

    state.subjects.forEach((subj) => {
      const opt1 = document.createElement('option');
      opt1.value = subj.id;
      opt1.textContent = subj.name;
      if (hwSelect) hwSelect.appendChild(opt1);

      const opt2 = document.createElement('option');
      opt2.value = subj.id;
      opt2.textContent = subj.name;
      if (reportSelect) reportSelect.appendChild(opt2);
    });

    if (hwSelect) {
      const customOpt = document.createElement('option');
      customOpt.value = 'custom';
      customOpt.textContent = '✏️ Ввести предмет вручную...';
      hwSelect.appendChild(customOpt);
    }

    // Заполняем фильтры-пилюли для ДЗ и докладов
    renderSubjectFilterPills(elements.hwSubjectsFilter, (subjId) => {
      state.selectedHwSubject = subjId;
      loadHomework();
    });

    renderSubjectFilterPills(elements.reportSubjectsFilter, (subjId) => {
      state.selectedReportSubject = subjId;
      loadReports();
    });
  }

  function renderSubjectFilterPills(container, onSelect) {
    if (!container) return;
    container.innerHTML = '';

    const allBtn = document.createElement('button');
    allBtn.className = 'pill-btn active';
    allBtn.type = 'button';
    allBtn.textContent = 'Все предметы';
    allBtn.dataset.subjectId = 'all';
    allBtn.addEventListener('click', () => {
      container.querySelectorAll('.pill-btn').forEach((b) => b.classList.remove('active'));
      allBtn.classList.add('active');
      triggerHaptic('light');
      onSelect('all');
    });
    container.appendChild(allBtn);

    state.subjects.forEach((subj) => {
      const btn = document.createElement('button');
      btn.className = 'pill-btn';
      btn.type = 'button';
      btn.textContent = subj.name;
      btn.dataset.subjectId = String(subj.id);
      btn.addEventListener('click', () => {
        container.querySelectorAll('.pill-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        triggerHaptic('light');
        onSelect(String(subj.id));
      });
      container.appendChild(btn);
    });
  }

  // ---------------- 3. МОДУЛЬ РАСПИСАНИЯ ---------------- //

  async function loadSchedule() {
    let days = [];
    try {
      const data = await apiFetch(`/api/schedule?week_type=${state.currentWeekType}`);
      days = data.days || [];
    } catch (err) {
      days = state.currentWeekType === 'current'
        ? DEFAULT_DAYS
        : DEFAULT_DAYS.map((d) => ({ ...d, content: 'Расписание на следующую неделю формируется' }));
    }

    if (!elements.scheduleDaysList) return;
    elements.scheduleDaysList.innerHTML = '';

    days.forEach((day) => {
      const card = document.createElement('div');
      card.className = 'day-card';

      const hasContent = Boolean(day.content && day.content.trim());
      const contentHtml = hasContent
        ? `<div class="day-content">${escapeHtml(day.content)}</div>`
        : `<div class="day-content empty">Нет пар или расписание ещё не заполнено</div>`;

      const editBtnHtml = state.isAdmin
        ? `<button class="btn btn-secondary btn-sm btn-edit-day" data-day-idx="${day.day_of_week}" data-day-name="${day.day_name}" type="button">✏️ Изменить</button>`
        : '';

      card.innerHTML = `
        <div class="day-card-header">
          <span class="day-name">📌 ${day.day_name}</span>
          ${editBtnHtml}
        </div>
        ${contentHtml}
      `;

      card.querySelector('.btn-edit-day')?.addEventListener('click', () => {
        elements.editScheduleTitle.textContent = `Редактирование: ${day.day_name}`;
        elements.editScheduleWeekType.value = state.currentWeekType;
        elements.editScheduleDayIdx.value = day.day_of_week;
        elements.editScheduleContent.value = day.content || '';
        openModal(elements.modalEditSchedule);
      });

      elements.scheduleDaysList.appendChild(card);
    });
  }

  function setupScheduleEvents() {
    elements.btnWeekCurrent?.addEventListener('click', () => {
      if (state.currentWeekType === 'current') return;
      state.currentWeekType = 'current';
      elements.btnWeekCurrent.classList.add('active');
      elements.btnWeekNext.classList.remove('active');
      triggerHaptic('light');
      loadSchedule();
    });

    elements.btnWeekNext?.addEventListener('click', () => {
      if (state.currentWeekType === 'next') return;
      state.currentWeekType = 'next';
      elements.btnWeekNext.classList.add('active');
      elements.btnWeekCurrent.classList.remove('active');
      triggerHaptic('light');
      loadSchedule();
    });

    elements.formEditSchedule?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const week_type = elements.editScheduleWeekType.value;
      const day_of_week = parseInt(elements.editScheduleDayIdx.value, 10);
      const content = elements.editScheduleContent.value.trim();

      try {
        await apiFetch('/api/schedule', {
          method: 'POST',
          body: JSON.stringify({ week_type, day_of_week, content }),
        });
        triggerHaptic('success');
        showToast('Расписание успешно сохранено!', 'success');
      } catch (err) {
        // Оффлайн сохранение в локальном стейте
        const target = DEFAULT_DAYS.find((d) => d.day_of_week === day_of_week);
        if (target) target.content = content;
        showToast('Расписание обновлено (предпросмотр)', 'info');
      }
      closeModal(elements.modalEditSchedule);
      loadSchedule();
    });

    document.getElementById('btnAdminRollover')?.addEventListener('click', async () => {
      const ok = await confirmDialog('Перенести расписание следующей недели на текущую? Слот следующей недели будет очищен.');
      if (!ok) return;

      try {
        await apiFetch('/api/schedule/rollover', { method: 'POST' });
        triggerHaptic('success');
        showToast('Расписание перенесено!', 'success');
      } catch (err) {
        showToast('Расписание перенесено (демо-режим)', 'info');
      }
      loadSchedule();
    });

    document.getElementById('btnAdminClearWeek')?.addEventListener('click', async () => {
      const weekTitle = state.currentWeekType === 'current' ? 'текущую' : 'следующую';
      const ok = await confirmDialog(`Вы уверены, что хотите очистить ${weekTitle} неделю?`);
      if (!ok) return;

      try {
        await apiFetch('/api/schedule/clear', {
          method: 'POST',
          body: JSON.stringify({ week_type: state.currentWeekType }),
        });
        triggerHaptic('success');
        showToast('Расписание очищено!', 'success');
      } catch (err) {
        DEFAULT_DAYS.forEach((d) => { d.content = ''; });
        showToast('Расписание очищено (демо-режим)', 'info');
      }
      loadSchedule();
    });
  }

  // ---------------- 4. МОДУЛЬ ДОМАШНЕГО ЗАДАНИЯ ---------------- //

  async function loadHomework() {
    let items = [];
    try {
      const url = state.selectedHwSubject !== 'all'
        ? `/api/homework?subject_id=${state.selectedHwSubject}`
        : '/api/homework';
      const data = await apiFetch(url);
      items = data.homework || [];
    } catch (err) {
      items = state.demoHomework;
      if (state.selectedHwSubject !== 'all') {
        const sid = parseInt(state.selectedHwSubject, 10);
        items = items.filter((h) => h.subject_id === sid);
      }
    }

    if (!elements.homeworkList) return;
    elements.homeworkList.innerHTML = '';

    if (items.length === 0) {
      elements.homeworkList.innerHTML = `
        <div class="day-card" style="text-align: center; padding: 30px;">
          <p style="color: var(--text-muted); font-size: 14px;">🎉 Нет активных домашних заданий по выбранному предмету.</p>
        </div>
      `;
      return;
    }

    items.forEach((hw) => {
      const card = document.createElement('div');
      card.className = 'hw-card';

      const adminActionsHtml = state.isAdmin
        ? `
          <div class="hw-actions">
            <button class="btn btn-secondary btn-sm btn-edit-hw" type="button">✏️ Изменить</button>
            <button class="btn btn-danger-outline btn-sm btn-del-hw" type="button">🗑 Удалить</button>
          </div>
        `
        : '';

      card.innerHTML = `
        <div class="hw-card-top">
          <span class="hw-subject-badge">📖 ${escapeHtml(hw.subject_name || 'Предмет')}</span>
          <span class="hw-due-badge">⏰ ${escapeHtml(hw.due_date)}</span>
        </div>
        <div class="hw-text">${escapeHtml(hw.task_text)}</div>
        ${adminActionsHtml}
      `;

      card.querySelector('.btn-edit-hw')?.addEventListener('click', () => {
        elements.modalHomeworkTitle.textContent = 'Редактировать ДЗ';
        elements.editHwId.value = hw.id;
        document.getElementById('groupHwSubject').style.display = 'none';
        elements.hwDueDate.value = hw.due_date;
        elements.hwTaskText.value = hw.task_text;
        openModal(elements.modalHomework);
      });

      card.querySelector('.btn-del-hw')?.addEventListener('click', async () => {
        const ok = await confirmDialog(`Удалить задание по предмету «${hw.subject_name}»?`);
        if (!ok) return;

        try {
          await apiFetch(`/api/homework/${hw.id}`, { method: 'DELETE' });
          triggerHaptic('success');
          showToast('Задание удалено', 'success');
        } catch (err) {
          state.demoHomework = state.demoHomework.filter((h) => h.id !== hw.id);
          showToast('Задание удалено (демо-режим)', 'info');
        }
        loadHomework();
      });

      elements.homeworkList.appendChild(card);
    });
  }

  function setupHomeworkEvents() {
    // Открытие модалки добавления ДЗ
    document.getElementById('btnOpenAddHwModal')?.addEventListener('click', () => {
      elements.modalHomeworkTitle.textContent = 'Новое домашнее задание';
      elements.editHwId.value = '';
      document.getElementById('groupHwSubject').style.display = 'block';
      if (elements.hwManualSubjectWrap) elements.hwManualSubjectWrap.classList.add('hidden');
      if (elements.hwManualSubjectInput) elements.hwManualSubjectInput.value = '';
      if (elements.hwSubjectSelect && elements.hwSubjectSelect.options.length > 0) {
        elements.hwSubjectSelect.selectedIndex = 0;
      }
      elements.formHomework.reset();
      openModal(elements.modalHomework);
    });

    // Переключение ручного ввода предмета кнопкой
    elements.btnToggleManualSubject?.addEventListener('click', () => {
      const isHidden = elements.hwManualSubjectWrap?.classList.contains('hidden');
      if (isHidden) {
        elements.hwManualSubjectWrap?.classList.remove('hidden');
        if (elements.hwSubjectSelect) elements.hwSubjectSelect.value = 'custom';
        elements.hwManualSubjectInput?.focus();
      } else {
        elements.hwManualSubjectWrap?.classList.add('hidden');
        if (elements.hwSubjectSelect && elements.hwSubjectSelect.options.length > 0) {
          elements.hwSubjectSelect.selectedIndex = 0;
        }
      }
    });

    // Обработка выбора "Ввести вручную..." в селекте
    elements.hwSubjectSelect?.addEventListener('change', () => {
      if (elements.hwSubjectSelect.value === 'custom') {
        elements.hwManualSubjectWrap?.classList.remove('hidden');
        elements.hwManualSubjectInput?.focus();
      } else {
        elements.hwManualSubjectWrap?.classList.add('hidden');
      }
    });

    elements.formHomework?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const hwId = elements.editHwId.value;
      const due_date = elements.hwDueDate.value.trim();
      const task_text = elements.hwTaskText.value.trim();

      const isManual = (elements.hwSubjectSelect?.value === 'custom') ||
        (elements.hwManualSubjectWrap && !elements.hwManualSubjectWrap.classList.contains('hidden') && elements.hwManualSubjectInput?.value.trim().length > 0);

      const manualSubjectName = elements.hwManualSubjectInput ? elements.hwManualSubjectInput.value.trim() : '';

      let payload = { due_date, task_text };
      let subject_name_to_use = '';
      let subject_id_to_use = null;

      if (!hwId) {
        if (isManual) {
          if (!manualSubjectName) {
            showToast('Пожалуйста, введите название предмета вручную', 'error');
            elements.hwManualSubjectInput?.focus();
            return;
          }
          payload.subject_name = manualSubjectName;
          subject_name_to_use = manualSubjectName;
        } else {
          subject_id_to_use = parseInt(elements.hwSubjectSelect.value, 10);
          payload.subject_id = subject_id_to_use;
          const found = state.subjects.find((s) => s.id === subject_id_to_use);
          subject_name_to_use = found ? found.name : 'Предмет';
        }
      }

      try {
        if (hwId) {
          await apiFetch(`/api/homework/${hwId}`, {
            method: 'PUT',
            body: JSON.stringify({ due_date, task_text }),
          });
          showToast('Домашнее задание обновлено!', 'success');
        } else {
          await apiFetch('/api/homework', {
            method: 'POST',
            body: JSON.stringify(payload),
          });
          showToast('Домашнее задание добавлено!', 'success');
          await loadSubjects();
        }
        triggerHaptic('success');
      } catch (err) {
        if (!hwId) {
          let sid = subject_id_to_use;
          if (isManual) {
            let existing = state.subjects.find((s) => s.name.toLowerCase() === manualSubjectName.toLowerCase());
            if (!existing) {
              sid = Date.now();
              state.subjects.push({ id: sid, name: manualSubjectName });
              renderSubjectFilterPills(elements.hwSubjectsFilter, (subjId) => {
                state.selectedHwSubject = subjId;
                loadHomework();
              });
            } else {
              sid = existing.id;
            }
          }
          state.demoHomework.unshift({
            id: Date.now(),
            subject_id: sid,
            subject_name: subject_name_to_use,
            due_date,
            task_text,
          });
        }
        showToast('Сохранено (демо-режим)', 'info');
      }
      closeModal(elements.modalHomework);
      loadHomework();
    });
  }

  // ---------------- 5. МОДУЛЬ ДОКЛАДОВ И ЧЕСТНОГО ДРОПА ---------------- //

  async function loadReports() {
    let batches = [];
    try {
      const url = state.selectedReportSubject !== 'all'
        ? `/api/reports/batches?subject_id=${state.selectedReportSubject}`
        : '/api/reports/batches';
      const data = await apiFetch(url);
      batches = data.batches || [];
    } catch (err) {
      batches = state.demoReports;
      if (state.selectedReportSubject !== 'all') {
        const sid = parseInt(state.selectedReportSubject, 10);
        batches = batches.filter((b) => b.subject_id === sid);
      }
    }

    if (!elements.reportsBatchesList) return;
    elements.reportsBatchesList.innerHTML = '';

    if (batches.length === 0) {
      elements.reportsBatchesList.innerHTML = `
        <div class="day-card" style="text-align: center; padding: 30px;">
          <p style="color: var(--text-muted); font-size: 14px;">📭 Пока нет доступных тем для докладов по этому предмету.</p>
        </div>
      `;
      return;
    }

    batches.forEach((batch) => {
      const card = document.createElement('div');
      card.className = 'batch-card';

      const isPublished = Boolean(batch.is_published);
      const statusHtml = isPublished
        ? `<span class="status-badge published">🟢 Опубликовано</span>`
        : `<span class="status-badge pending">⏳ Дроп: ${escapeHtml(batch.release_date || '')} <i>(время засекречено)</i></span>`;

      let adminControlsHtml = '';
      if (state.isAdmin) {
        const publishNowBtn = !isPublished
          ? `<button class="btn btn-success btn-sm btn-publish-batch" data-batch-id="${batch.id}" type="button">🚀 Выложить сейчас</button>`
          : '';
        adminControlsHtml = `
          <div class="batch-admin-controls">
            ${publishNowBtn}
            <button class="btn btn-danger-outline btn-sm btn-delete-batch" data-batch-id="${batch.id}" type="button">🗑 Удалить пул</button>
          </div>
        `;
      }

      const topics = batch.topics || [];
      let topicsHtml = '<div class="topics-list">';
      topics.forEach((t) => {
        let itemClass = 'topic-item';
        let statusLabel = '';
        let actionBtn = '';

        if (t.is_mine) {
          itemClass += ' mine';
          statusLabel = `<span class="topic-status-label mine">⭐️ Ваша тема</span>`;
          actionBtn = `<button class="btn btn-danger-outline btn-sm btn-unclaim-topic" data-batch-id="${batch.id}" data-topic-id="${t.id}" type="button">Отказаться</button>`;
        } else if (t.is_taken) {
          itemClass += ' taken';
          statusLabel = `<span class="topic-status-label taken">✅ Занято: <b>${escapeHtml(t.student_name || 'Студент')}</b></span>`;
        } else {
          statusLabel = `<span class="topic-status-label free">🟢 Свободно</span>`;
          if (isPublished) {
            actionBtn = `<button class="btn btn-primary btn-sm btn-claim-topic" data-batch-id="${batch.id}" data-topic-id="${t.id}" type="button">Занять тему</button>`;
          }
        }

        topicsHtml += `
          <div class="${itemClass}">
            <div class="topic-main">
              <span class="topic-num">${t.topic_number}</span>
              <span class="topic-title">${escapeHtml(t.topic_text)}</span>
            </div>
            <div class="topic-footer">
              ${statusLabel}
              ${actionBtn}
            </div>
          </div>
        `;
      });
      topicsHtml += '</div>';

      card.innerHTML = `
        <div class="batch-header">
          <div>
            <h3 class="batch-subject">🎤 ${escapeHtml(batch.subject_name || 'Предмет')}</h3>
            <p class="batch-seminar-date">🗓 Семинар: <b>${escapeHtml(batch.seminar_date)}</b></p>
          </div>
          ${statusHtml}
        </div>
        ${adminControlsHtml}
        ${topicsHtml}
      `;

      // Обработка кнопки "Занять тему"
      card.querySelectorAll('.btn-claim-topic').forEach((btn) => {
        btn.addEventListener('click', async () => {
          const topicId = btn.getAttribute('data-topic-id');
          try {
            await apiFetch(`/api/reports/topics/${topicId}/claim`, { method: 'POST' });
            triggerHaptic('success');
            showToast('Поздравляем! Вы успешно заняли тему.', 'success');
          } catch (err) {
            // Оффлайн обработка
            const bId = parseInt(btn.getAttribute('data-batch-id'), 10);
            const b = state.demoReports.find((x) => x.id === bId);
            const top = b?.topics.find((x) => String(x.id) === String(topicId));
            if (top) {
              top.is_taken = true;
              top.is_mine = true;
              top.student_name = state.user?.full_name || 'Вы';
            }
            triggerHaptic('success');
            showToast('Тема занята (демо-режим)', 'success');
          }
          loadReports();
        });
      });

      // Обработка кнопки "Отказаться"
      card.querySelectorAll('.btn-unclaim-topic').forEach((btn) => {
        btn.addEventListener('click', async () => {
          const topicId = btn.getAttribute('data-topic-id');
          const ok = await confirmDialog('Вы уверены, что хотите отказаться от этой темы?');
          if (!ok) return;

          try {
            await apiFetch(`/api/reports/topics/${topicId}/unclaim`, { method: 'POST' });
            triggerHaptic('success');
            showToast('Вы отказались от темы. Она снова свободна.', 'info');
          } catch (err) {
            const bId = parseInt(btn.getAttribute('data-batch-id'), 10);
            const b = state.demoReports.find((x) => x.id === bId);
            const top = b?.topics.find((x) => String(x.id) === String(topicId));
            if (top) {
              top.is_taken = false;
              top.is_mine = false;
              top.student_name = null;
            }
            showToast('Тема освобождена (демо-режим)', 'info');
          }
          loadReports();
        });
      });

      // Досрочная публикация пула
      card.querySelector('.btn-publish-batch')?.addEventListener('click', async () => {
        const ok = await confirmDialog('Опубликовать темы прямо сейчас и разослать уведомления группе?');
        if (!ok) return;

        try {
          await apiFetch(`/api/reports/batches/${batch.id}/publish`, { method: 'POST' });
          triggerHaptic('success');
          showToast('Темы опубликованы! Уведомления отправлены.', 'success');
        } catch (err) {
          batch.is_published = 1;
          showToast('Опубликовано (демо-режим)', 'info');
        }
        loadReports();
      });

      // Удаление пула
      card.querySelector('.btn-delete-batch')?.addEventListener('click', async () => {
        const ok = await confirmDialog('Удалить весь пул тем для докладов?');
        if (!ok) return;

        try {
          await apiFetch(`/api/reports/batches/${batch.id}`, { method: 'DELETE' });
          triggerHaptic('success');
          showToast('Пул докладов удалён', 'success');
        } catch (err) {
          state.demoReports = state.demoReports.filter((b) => b.id !== batch.id);
          showToast('Пул удалён (демо-режим)', 'info');
        }
        loadReports();
      });

      elements.reportsBatchesList.appendChild(card);
    });
  }

  function setupReportsEvents() {
    document.getElementById('btnOpenAddReportModal')?.addEventListener('click', () => {
      elements.formReportBatch?.reset();
      openModal(elements.modalReportBatch);
    });

    elements.formReportBatch?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const subject_id = parseInt(elements.reportSubjectSelect.value, 10);
      const seminar_date = elements.reportSeminarDate.value.trim();
      const release_date = elements.reportReleaseDate.value.trim();
      const topicsText = elements.reportTopicsText.value.trim();

      const topics = topicsText
        .split('\n')
        .map((t) => t.trim())
        .filter((t) => t.length > 0);

      if (topics.length === 0) {
        showToast('Введите хотя бы одну тему', 'error');
        return;
      }

      try {
        const res = await apiFetch('/api/reports/batches', {
          method: 'POST',
          body: JSON.stringify({ subject_id, seminar_date, release_date, topics }),
        });
        triggerHaptic('success');
        showToast(res.message || 'Пул докладов запланирован!', 'success');
      } catch (err) {
        const subj = state.subjects.find((s) => s.id === subject_id);
        state.demoReports.unshift({
          id: Date.now(),
          subject_id,
          subject_name: subj ? subj.name : 'Предмет',
          seminar_date,
          is_published: 0,
          release_date,
          release_datetime_random: null,
          topics: topics.map((t, idx) => ({
            id: Date.now() + idx,
            topic_number: idx + 1,
            topic_text: t,
            is_taken: false,
            student_name: null,
            is_mine: false,
          })),
        });
        showToast('Пул запланирован (демо-режим)', 'info');
      }
      closeModal(elements.modalReportBatch);
      loadReports();
    });
  }

  // ---------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---------------- //

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  async function reloadAll() {
    await loadUser();
    await loadSubjects();
    await loadSchedule();
    await loadHomework();
    await loadReports();
  }

  // Запуск при загрузке DOM
  document.addEventListener('DOMContentLoaded', async () => {
    setupTabs();
    setupDevModeSwitch();
    setupScheduleEvents();
    setupHomeworkEvents();
    setupReportsEvents();
    await reloadAll();
  });
})();
