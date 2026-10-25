/**
 * HomeWorker Telegram Mini App — Клиентская логика приложения (Vanilla JS)
 */

(function () {
  'use strict';

  // 1. Инициализация Telegram WebApp SDK
  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
    try {
      tg.setHeaderColor('#0b0f17');
      tg.setBackgroundColor('#0b0f17');
    } catch (e) {}
  }

  // 2. Внутреннее состояние приложения
  const state = {
    user: null,
    isAdmin: false,
    currentWeekType: 'current',
    selectedHwSubject: 'all',
    selectedReportSubject: 'all',
    subjects: [],
    // Режим разработки для обычных браузеров
    devTelegramId: '999888', // по умолчанию ID старосты для тестов в браузере
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
        tg.HapticFeedback.impactOccurred(type); // light, medium, heavy
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

  // Вспомогательный клиент API
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

    try {
      const resp = await fetch(endpoint, { ...options, headers });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || `Ошибка сервера: ${resp.status}`);
      }
      return data;
    } catch (err) {
      console.error(`API Error [${endpoint}]:`, err);
      throw err;
    }
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

  // Закрытие модалок по клику на крестик или фон
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

    // Быстрые кнопки в панели старосты
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

      elements.userBadge.classList.remove('skeleton');
      elements.userName.textContent = state.user.full_name || `ID: ${state.user.telegram_id}`;

      if (state.isAdmin) {
        elements.userRole.textContent = '👑 Староста';
        elements.userRole.classList.add('admin');
        elements.navItemAdmin?.classList.remove('hidden');
        elements.adminScheduleBar?.classList.remove('hidden');
        document.querySelectorAll('.admin-only').forEach((el) => el.classList.remove('hidden'));
      } else {
        elements.userRole.textContent = 'Студент';
        elements.userRole.classList.remove('admin');
        elements.navItemAdmin?.classList.add('hidden');
        elements.adminScheduleBar?.classList.add('hidden');
        document.querySelectorAll('.admin-only').forEach((el) => el.classList.add('hidden'));
      }
    } catch (err) {
      showToast('Не удалось войти в аккаунт: ' + err.message, 'error');
    }
  }

  function setupDevModeSwitch() {
    if (!state.isTelegram) {
      elements.devModeBar?.classList.remove('hidden');

      elements.devBtnStudent?.addEventListener('click', async () => {
        state.devTelegramId = '111222';
        elements.devBtnStudent.classList.add('active');
        elements.devBtnAdmin.classList.remove('active');
        await reloadAll();
      });

      elements.devBtnAdmin?.addEventListener('click', async () => {
        state.devTelegramId = '999888';
        elements.devBtnAdmin.classList.add('active');
        elements.devBtnStudent.classList.remove('active');
        await reloadAll();
      });
    }
  }

  // ---------------- 2. МОДУЛЬ ПРЕДМЕТОВ ---------------- //

  async function loadSubjects() {
    try {
      const data = await apiFetch('/api/subjects');
      state.subjects = data.subjects || [];

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

      // Заполняем фильтры-пилюли для ДЗ и докладов
      renderSubjectFilterPills(elements.hwSubjectsFilter, (subjId) => {
        state.selectedHwSubject = subjId;
        loadHomework();
      });

      renderSubjectFilterPills(elements.reportSubjectsFilter, (subjId) => {
        state.selectedReportSubject = subjId;
        loadReports();
      });
    } catch (err) {
      console.error('Ошибка загрузки предметов:', err);
    }
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
    try {
      const data = await apiFetch(`/api/schedule?week_type=${state.currentWeekType}`);
      const days = data.days || [];
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

        // Клик по кнопке редактирования дня
        card.querySelector('.btn-edit-day')?.addEventListener('click', () => {
          elements.editScheduleTitle.textContent = `Редактирование: ${day.day_name}`;
          elements.editScheduleWeekType.value = state.currentWeekType;
          elements.editScheduleDayIdx.value = day.day_of_week;
          elements.editScheduleContent.value = day.content || '';
          openModal(elements.modalEditSchedule);
        });

        elements.scheduleDaysList.appendChild(card);
      });
    } catch (err) {
      elements.scheduleDaysList.innerHTML = `<div class="info-banner error"><p>Ошибка загрузки расписания: ${err.message}</p></div>`;
    }
  }

  function setupScheduleEvents() {
    // Переключение Текущая / Следующая неделя
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

    // Отправка формы редактирования дня
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
        closeModal(elements.modalEditSchedule);
        loadSchedule();
      } catch (err) {
        triggerHaptic('error');
        showToast('Ошибка: ' + err.message, 'error');
      }
    });

    // Перенос недели старостой
    document.getElementById('btnAdminRollover')?.addEventListener('click', async () => {
      const ok = await confirmDialog('Перенести расписание следующей недели на текущую? Слот следующей недели будет очищен.');
      if (!ok) return;

      try {
        await apiFetch('/api/schedule/rollover', { method: 'POST' });
        triggerHaptic('success');
        showToast('Расписание успешно перенесено!', 'success');
        loadSchedule();
      } catch (err) {
        showToast('Ошибка переноса: ' + err.message, 'error');
      }
    });

    // Очистка недели старостой
    document.getElementById('btnAdminClearWeek')?.addEventListener('click', async () => {
      const weekTitle = state.currentWeekType === 'current' ? 'текущую' : 'следующую';
      const ok = await confirmDialog(`Вы уверены, что хотите полностью очистить ${weekTitle} неделю?`);
      if (!ok) return;

      try {
        await apiFetch('/api/schedule/clear', {
          method: 'POST',
          body: JSON.stringify({ week_type: state.currentWeekType }),
        });
        triggerHaptic('success');
        showToast(`Расписание очищено!`, 'success');
        loadSchedule();
      } catch (err) {
        showToast('Ошибка очистки: ' + err.message, 'error');
      }
    });
  }

  // ---------------- 4. МОДУЛЬ ДОМАШНЕГО ЗАДАНИЯ ---------------- //

  async function loadHomework() {
    try {
      const url = state.selectedHwSubject !== 'all'
        ? `/api/homework?subject_id=${state.selectedHwSubject}`
        : '/api/homework';

      const data = await apiFetch(url);
      const items = data.homework || [];
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

        // Кнопка редактирования ДЗ
        card.querySelector('.btn-edit-hw')?.addEventListener('click', () => {
          elements.modalHomeworkTitle.textContent = 'Редактировать ДЗ';
          elements.editHwId.value = hw.id;
          document.getElementById('groupHwSubject').style.display = 'none';
          elements.hwDueDate.value = hw.due_date;
          elements.hwTaskText.value = hw.task_text;
          openModal(elements.modalHomework);
        });

        // Кнопка удаления ДЗ
        card.querySelector('.btn-del-hw')?.addEventListener('click', async () => {
          const ok = await confirmDialog(`Удалить домашнее задание по предмету «${hw.subject_name}»?`);
          if (!ok) return;

          try {
            await apiFetch(`/api/homework/${hw.id}`, { method: 'DELETE' });
            triggerHaptic('success');
            showToast('Задание удалено', 'success');
            loadHomework();
          } catch (err) {
            showToast('Ошибка удаления: ' + err.message, 'error');
          }
        });

        elements.homeworkList.appendChild(card);
      });
    } catch (err) {
      elements.homeworkList.innerHTML = `<div class="info-banner error"><p>Ошибка загрузки ДЗ: ${err.message}</p></div>`;
    }
  }

  function setupHomeworkEvents() {
    // Открытие модалки добавления ДЗ
    document.getElementById('btnOpenAddHwModal')?.addEventListener('click', () => {
      elements.modalHomeworkTitle.textContent = 'Добавить домашнее задание';
      elements.editHwId.value = '';
      document.getElementById('groupHwSubject').style.display = 'block';
      elements.hwDueDate.value = '';
      elements.hwTaskText.value = '';
      openModal(elements.modalHomework);
    });

    // Отправка формы ДЗ (создание или обновление)
    elements.formHomework?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const hwId = elements.editHwId.value;
      const due_date = elements.hwDueDate.value.trim();
      const task_text = elements.hwTaskText.value.trim();

      try {
        if (hwId) {
          // Редактирование
          await apiFetch(`/api/homework/${hwId}`, {
            method: 'PUT',
            body: JSON.stringify({ due_date, task_text }),
          });
          showToast('Домашнее задание обновлено!', 'success');
        } else {
          // Создание
          const subject_id = parseInt(elements.hwSubjectSelect.value, 10);
          await apiFetch('/api/homework', {
            method: 'POST',
            body: JSON.stringify({ subject_id, due_date, task_text }),
          });
          showToast('Домашнее задание добавлено!', 'success');
        }

        triggerHaptic('success');
        closeModal(elements.modalHomework);
        loadHomework();
      } catch (err) {
        triggerHaptic('error');
        showToast('Ошибка: ' + err.message, 'error');
      }
    });
  }

  // ---------------- 5. МОДУЛЬ ДОКЛАДОВ (ЧЕСТНЫЙ ДРОП И ЗАПИСЬ) ---------------- //

  async function loadReports() {
    try {
      const url = state.selectedReportSubject !== 'all'
        ? `/api/reports/batches?subject_id=${state.selectedReportSubject}`
        : '/api/reports/batches';

      const data = await apiFetch(url);
      const batches = data.batches || [];
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
          : `<span class="status-badge pending">⏳ Дроп: ${escapeHtml(batch.release_datetime_random || batch.release_date)}</span>`;

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

        // Темы внутри пула
        const topics = batch.topics || [];
        let topicsHtml = '<div class="topics-list">';
        topics.forEach((t) => {
          let itemClass = 'topic-item';
          let statusLabel = '';
          let actionBtn = '';

          if (t.is_mine) {
            itemClass += ' mine';
            statusLabel = `<span class="topic-status-label mine">⭐️ Ваша тема</span>`;
            actionBtn = `<button class="btn btn-danger-outline btn-sm btn-unclaim-topic" data-topic-id="${t.id}" type="button">Отказаться</button>`;
          } else if (t.is_taken) {
            itemClass += ' taken';
            statusLabel = `<span class="topic-status-label taken">✅ Занято: <b>${escapeHtml(t.student_name || 'Студент')}</b></span>`;
          } else {
            statusLabel = `<span class="topic-status-label free">🟢 Свободно</span>`;
            if (isPublished) {
              actionBtn = `<button class="btn btn-primary btn-sm btn-claim-topic" data-topic-id="${t.id}" type="button">Занять тему</button>`;
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

        // Кнопка занятия темы
        card.querySelectorAll('.btn-claim-topic').forEach((btn) => {
          btn.addEventListener('click', async () => {
            const topicId = btn.getAttribute('data-topic-id');
            btn.disabled = true;
            btn.textContent = 'Занимаем...';

            try {
              await apiFetch(`/api/reports/topics/${topicId}/claim`, { method: 'POST' });
              triggerHaptic('success');
              showToast('Тема успешно закреплена за вами!', 'success');
              loadReports();
            } catch (err) {
              triggerHaptic('error');
              showToast(err.message, 'error');
              loadReports();
            }
          });
        });

        // Кнопка отказа от темы
        card.querySelectorAll('.btn-unclaim-topic').forEach((btn) => {
          btn.addEventListener('click', async () => {
            const topicId = btn.getAttribute('data-topic-id');
            const ok = await confirmDialog('Вы уверены, что хотите отказаться от этой темы доклада?');
            if (!ok) return;

            try {
              await apiFetch(`/api/reports/topics/${topicId}/unclaim`, { method: 'POST' });
              triggerHaptic('light');
              showToast('Вы отказались от темы', 'info');
              loadReports();
            } catch (err) {
              showToast('Ошибка: ' + err.message, 'error');
            }
          });
        });

        // Досрочная публикация старостой
        card.querySelector('.btn-publish-batch')?.addEventListener('click', async (e) => {
          const batchId = e.currentTarget.getAttribute('data-batch-id');
          const ok = await confirmDialog('Опубликовать темы прямо сейчас и разослать группе уведомление?');
          if (!ok) return;

          try {
            await apiFetch(`/api/reports/batches/${batchId}/publish`, { method: 'POST' });
            triggerHaptic('success');
            showToast('Темы опубликованы и разосланы группе!', 'success');
            loadReports();
          } catch (err) {
            showToast('Ошибка: ' + err.message, 'error');
          }
        });

        // Удаление пула старостой
        card.querySelector('.btn-delete-batch')?.addEventListener('click', async (e) => {
          const batchId = e.currentTarget.getAttribute('data-batch-id');
          const ok = await confirmDialog('Удалить этот пул тем докладов?');
          if (!ok) return;

          try {
            await apiFetch(`/api/reports/batches/${batchId}`, { method: 'DELETE' });
            triggerHaptic('success');
            showToast('Пул докладов удален', 'success');
            loadReports();
          } catch (err) {
            showToast('Ошибка удаления: ' + err.message, 'error');
          }
        });

        elements.reportsBatchesList.appendChild(card);
      });
    } catch (err) {
      elements.reportsBatchesList.innerHTML = `<div class="info-banner error"><p>Ошибка загрузки докладов: ${err.message}</p></div>`;
    }
  }

  function setupReportsEvents() {
    // Открытие модалки создания тем докладов
    document.getElementById('btnOpenAddReportModal')?.addEventListener('click', () => {
      elements.reportSeminarDate.value = '';
      elements.reportReleaseDate.value = '';
      elements.reportTopicsText.value = '';
      openModal(elements.modalReportBatch);
    });

    // Отправка формы создания пула докладов
    elements.formReportBatch?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const subject_id = parseInt(elements.reportSubjectSelect.value, 10);
      const seminar_date = elements.reportSeminarDate.value.trim();
      const release_date = elements.reportReleaseDate.value.trim();
      const topics = elements.reportTopicsText.value
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
        showToast(res.message || 'Пул докладов успешно запланирован!', 'success');
        closeModal(elements.modalReportBatch);
        loadReports();
      } catch (err) {
        triggerHaptic('error');
        showToast('Ошибка: ' + err.message, 'error');
      }
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

  // Запуск при загрузке документа
  document.addEventListener('DOMContentLoaded', async () => {
    setupTabs();
    setupDevModeSwitch();
    setupScheduleEvents();
    setupHomeworkEvents();
    setupReportsEvents();
    await reloadAll();
  });
})();
