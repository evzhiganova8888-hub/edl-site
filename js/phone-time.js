function updatePhoneTime() {
  const now = new Date();
  const timeStr = now.toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit'
  });
  
  // Короткое название таймзоны
  const offsetMin = -now.getTimezoneOffset();
  const offsetH = Math.floor(Math.abs(offsetMin) / 60);
  const sign = offsetMin >= 0 ? '+' : '−';
  const tzShort = `UTC${sign}${offsetH}`;
  
  const timeEl = document.querySelector('.phone-time');
  const tzEl = document.querySelector('.phone-tz');
  
  if (timeEl) timeEl.textContent = timeStr;
  if (tzEl) tzEl.textContent = `сегодня · ${tzShort}`;
}

// Запуск и обновление каждые 30 секунд
document.addEventListener("DOMContentLoaded", () => {
    updatePhoneTime();
    setInterval(updatePhoneTime, 30000);
});
