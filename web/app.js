const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
      }
    });
  },
  { threshold: 0.18, rootMargin: '0px 0px -8% 0px' }
);

const revealEls = document.querySelectorAll('.reveal');
revealEls.forEach((el) => observer.observe(el));

const railDots = document.querySelectorAll('.rail-dot');
const sections = ['hero', 'upload', 'story', 'clips', 'render'];

const setActiveRail = () => {
  const scrollMid = window.scrollY + window.innerHeight * 0.35;
  let activeId = 'hero';

  sections.forEach((id) => {
    const el = document.getElementById(id);
    if (el && scrollMid >= el.offsetTop) {
      activeId = id;
    }
  });

  railDots.forEach((dot) => {
    dot.classList.toggle('active', dot.dataset.target === activeId);
  });
};

railDots.forEach((dot) => {
  dot.addEventListener('click', () => {
    const target = document.getElementById(dot.dataset.target);
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});

window.addEventListener('scroll', setActiveRail, { passive: true });
setActiveRail();

const templateInput = document.getElementById('fileTemplate');
const templateInfo = document.getElementById('templateInfo');

if (templateInput) {
  templateInput.addEventListener('change', (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;

    const sizeMB = (file.size / 1024 / 1024).toFixed(1);
    templateInfo.textContent = `${file.name} • ${sizeMB} MB`;
    templateInfo.classList.remove('hidden');
  });
}

const aurora = document.getElementById('aurora');
if (aurora && aurora.getContext) {
  const ctx = aurora.getContext('2d');
  const dpr = window.devicePixelRatio || 1;

  const resize = () => {
    aurora.width = window.innerWidth * dpr;
    aurora.height = window.innerHeight * dpr;
    aurora.style.width = window.innerWidth + 'px';
    aurora.style.height = window.innerHeight + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  };

  const draw = () => {
    const w = window.innerWidth;
    const h = window.innerHeight;
    ctx.clearRect(0, 0, w, h);

    const gradient = ctx.createRadialGradient(
      w * 0.25,
      h * 0.2,
      60,
      w * 0.25,
      h * 0.2,
      w * 0.8
    );
    gradient.addColorStop(0, 'rgba(241, 199, 122, 0.18)');
    gradient.addColorStop(0.4, 'rgba(130, 170, 255, 0.1)');
    gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');

    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, w, h);

    const blurs = [
      { x: w * 0.18, y: h * 0.3, r: 200, a: 0.14 },
      { x: w * 0.72, y: h * 0.2, r: 240, a: 0.12 },
      { x: w * 0.5, y: h * 0.8, r: 260, a: 0.08 }
    ];

    blurs.forEach((b, index) => {
      const g = ctx.createRadialGradient(b.x, b.y, 20, b.x, b.y, b.r);
      g.addColorStop(0, `rgba(241, 199, 122, ${b.a})`);
      g.addColorStop(0.45, `rgba(145, 125, 240, ${b.a * 0.6})`);
      g.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = g;
      ctx.fillRect(b.x - b.r, b.y - b.r, b.r * 2, b.r * 2 + 50);
    });
  };

  resize();
  draw();
  window.addEventListener('resize', () => {
    resize();
    draw();
  });
}
