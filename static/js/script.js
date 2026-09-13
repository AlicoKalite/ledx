document.addEventListener('DOMContentLoaded', () => {
  document.title = document.title.replace(/rezervia/gi, 'Aliek');
  document.querySelectorAll('body *').forEach(element => {
    element.childNodes.forEach(node => {
      if (node.nodeType === Node.TEXT_NODE) node.textContent = node.textContent.replace(/rezervia/gi, 'Aliek');
    });
  });

  const ledCopy = document.querySelector('.led-copy');
  if (ledCopy) ledCopy.innerHTML = '<strong>Aliek</strong>';
  document.querySelectorAll('.feature-visual span, .feature-card a').forEach(element => element.remove());

  const serviceCards = document.querySelectorAll('.feature-card');
  if (serviceCards.length >= 3) {
    const combinedCard = serviceCards[1];
    const servicesHeading = document.querySelector('#services h2');
    if (servicesHeading) servicesHeading.textContent = 'Sahnenin iki temel katmanı';
    combinedCard.querySelector('h3').textContent = 'Ses ve sahne ışıkları';
    combinedCard.querySelector('p').textContent = 'Konuşma, müzik ve canlı performanslar için güçlü ses; spot, beam ve efekt ışıklarıyla tamamlanan sahne kurulumu.';
    serviceCards[0].closest('.col-md-4').classList.replace('col-md-4', 'col-md-6');
    combinedCard.closest('.col-md-4').classList.replace('col-md-4', 'col-md-6');
    serviceCards[2].closest('.col-md-4').remove();
  }

  [['feature-led', 'sahne-1.jpg', 'LED ekranli sahne kurulumu'], ['feature-sound', 'sahne-2.jpg', 'Ses ve sahne isiklari kurulumu']].forEach(([cardClass, fileName, altText]) => {
    const visual = document.querySelector(`.${cardClass} .feature-visual`);
    if (!visual) return;
    visual.querySelector('b')?.remove();
    const image = document.createElement('img');
    image.src = `/static/images/${fileName}`;
    image.alt = altText;
    visual.prepend(image);
  });

  const form = document.querySelector('#reservation-form');
  if (!form) return;
  const fields = ['start_date', 'end_date', 'people_count', 'led_area', 'light_count'].map(id => document.getElementById(id));
  const price = document.getElementById('quote-price');
  const days = document.getElementById('quote-days');
  const updateQuote = async () => {
    const params = new URLSearchParams();
    fields.forEach(field => { if (field) params.set(field.name, field.value); });
    if (!params.get('start_date') || !params.get('end_date')) return;
    try {
      const response = await fetch(`/api/quote?${params}`);
      const data = await response.json();
      if (data.error) { price.textContent = '-- TL'; days.textContent = data.error; return; }
      price.textContent = `${Number(data.price).toLocaleString('tr-TR')} TL`;
      days.textContent = data.available ? `${data.days} günlük süre için tahmini tutar` : 'Bu tarihlerde müsaitlik yok';
      price.style.color = data.available ? '#d9ed92' : '#ffb4ab';
    } catch (_) { days.textContent = 'Fiyat şu anda hesaplanamadı.'; }
  };
  fields.forEach(field => field && field.addEventListener('change', updateQuote));
  fields.forEach(field => field && field.addEventListener('input', updateQuote));
});
