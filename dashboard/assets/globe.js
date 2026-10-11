/**
 * AnomIQ — 3D Infrastructure Holographic Globe & Network Engine
 * Clean, modern AI SaaS visual direction:
 * Deep navy sphere, luminous cyan & electric blue particles, subtle glowing flight arcs.
 */

class HoloGlobeEngine {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');

    this.autoRotate = true;
    this.rotationSpeed = 0.003;

    // 3D Globe Parameters
    this.radius = 145;
    this.rotX = 0.22;
    this.rotY = -0.55;
    this.targetRotX = 0.22;
    this.targetRotY = -0.55;
    this.zoom = 1.0;
    this.targetZoom = 1.0;

    // Drag / Orbit state
    this.isDragging = false;
    this.lastMouseX = 0;
    this.lastMouseY = 0;
    this.hoveredNode = null;

    // Global Clusters (Lat, Lon)
    this.clusters = [
      {
        id: 'us-east-1',
        name: 'us-east-k8s-prod',
        region: 'US East (N. Virginia)',
        lat: 38.89,
        lon: -77.03,
        status: 'critical',
        latency: '428ms',
        pods: '584 Pods',
        issue: 'P1 Memory Leak in checkout-gateway',
        color: '#f43f5e',
        glowColor: 'rgba(244, 63, 94, 0.7)',
        pulse: 0
      },
      {
        id: 'eu-central-1',
        name: 'eu-west-k8s-prod',
        region: 'Frankfurt (Germany)',
        lat: 50.11,
        lon: 8.68,
        status: 'healthy',
        latency: '34ms',
        pods: '462 Pods',
        issue: 'Nominal Operations',
        color: '#10b981',
        glowColor: 'rgba(16, 185, 129, 0.7)',
        pulse: 0
      },
      {
        id: 'ap-northeast-1',
        name: 'ap-east-k8s-edge',
        region: 'Tokyo (Japan)',
        lat: 35.68,
        lon: 139.69,
        status: 'healthy',
        latency: '41ms',
        pods: '436 Pods',
        issue: 'Nominal Operations',
        color: '#10b981',
        glowColor: 'rgba(16, 185, 129, 0.7)',
        pulse: 0
      },
      {
        id: 'ap-southeast-1',
        name: 'ap-south-edge',
        region: 'Singapore',
        lat: 1.35,
        lon: 103.82,
        status: 'healthy',
        latency: '48ms',
        pods: '210 Pods',
        issue: 'Nominal Operations',
        color: '#38bdf8',
        glowColor: 'rgba(56, 189, 248, 0.7)',
        pulse: 0
      },
      {
        id: 'eu-west-1',
        name: 'eu-west-ingress',
        region: 'London (UK)',
        lat: 51.50,
        lon: -0.12,
        status: 'healthy',
        latency: '22ms',
        pods: '390 Pods',
        issue: 'Nominal Operations',
        color: '#38bdf8',
        glowColor: 'rgba(56, 189, 248, 0.7)',
        pulse: 0
      }
    ];

    // Flight Arcs
    this.arcs = [
      { from: 0, to: 1, packets: [0.15, 0.65], speed: 0.007 },
      { from: 1, to: 2, packets: [0.35, 0.85], speed: 0.006 },
      { from: 0, to: 4, packets: [0.2], speed: 0.008 },
      { from: 2, to: 3, packets: [0.4], speed: 0.006 },
      { from: 3, to: 1, packets: [0.55], speed: 0.005 }
    ];

    this.dots = this.generateContinentDots();
    this.initEvents();
    this.resize();
    this.render = this.render.bind(this);
    requestAnimationFrame(this.render);
  }

  generateContinentDots() {
    const dots = [];
    const count = 1000;
    const phi = Math.PI * (3 - Math.sqrt(5));
    for (let i = 0; i < count; i++) {
      const y = 1 - (i / (count - 1)) * 2;
      const radiusAtY = Math.sqrt(1 - y * y);
      const theta = phi * i;
      const x = Math.cos(theta) * radiusAtY;
      const z = Math.sin(theta) * radiusAtY;

      const lat = Math.asin(y) * (180 / Math.PI);
      const lon = Math.atan2(z, x) * (180 / Math.PI);

      if (this.isRoughLandmass(lat, lon)) {
        dots.push({ x, y, z, lat, lon, size: 1.1 + Math.random() * 0.7, alpha: 0.4 + Math.random() * 0.45 });
      } else if (Math.random() < 0.07) {
        dots.push({ x, y, z, lat, lon, size: 0.8, alpha: 0.12 });
      }
    }
    return dots;
  }

  isRoughLandmass(lat, lon) {
    if (lat > 15 && lat < 70 && lon > -165 && lon < -50) return true; // North America
    if (lat > -55 && lat < 12 && lon > -82 && lon < -34) return true;  // South America
    if (lat > 35 && lat < 70 && lon > -10 && lon < 45) return true;   // Europe
    if (lat > -35 && lat < 36 && lon > -18 && lon < 50) return true;  // Africa
    if (lat > 5 && lat < 72 && lon > 45 && lon < 150) return true;    // Asia
    if (lat > -42 && lat < -10 && lon > 112 && lon < 154) return true;// Australia
    return false;
  }

  initEvents() {
    window.addEventListener('resize', () => this.resize());

    this.canvas.addEventListener('mousedown', (e) => {
      this.isDragging = true;
      this.lastMouseX = e.clientX;
      this.lastMouseY = e.clientY;
    });

    window.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      if (this.isDragging) {
        const dx = e.clientX - this.lastMouseX;
        const dy = e.clientY - this.lastMouseY;
        this.targetRotY += dx * 0.006;
        this.targetRotX += dy * 0.006;
        this.lastMouseX = e.clientX;
        this.lastMouseY = e.clientY;
      } else {
        this.checkHover(mouseX, mouseY);
      }
    });

    window.addEventListener('mouseup', () => {
      this.isDragging = false;
    });

    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      this.targetZoom += e.deltaY * -0.001;
      this.targetZoom = Math.max(0.75, Math.min(1.5, this.targetZoom));
    }, { passive: false });

    // Tooltip CTA button
    const investBtn = document.getElementById('tooltipInvestigateBtn');
    if (investBtn) {
      investBtn.addEventListener('click', () => {
        const rcaTab = document.getElementById('tabRca');
        if (rcaTab) rcaTab.click();
      });
    }
  }

  resize() {
    if (!this.canvas) return;
    const rect = this.canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.ctx.scale(dpr, dpr);
    this.displayWidth = rect.width;
    this.displayHeight = rect.height;
    this.centerX = this.displayWidth / 2;
    this.centerY = this.displayHeight / 2;
  }

  latLonTo3D(lat, lon, r) {
    const phi = (90 - lat) * (Math.PI / 180);
    const theta = (lon + 180) * (Math.PI / 180);
    return {
      x: -(r * Math.sin(phi) * Math.cos(theta)),
      y: r * Math.cos(phi),
      z: r * Math.sin(phi) * Math.sin(theta)
    };
  }

  rotate3D(p, rx, ry) {
    const cosY = Math.cos(ry);
    const sinY = Math.sin(ry);
    const x1 = p.x * cosY + p.z * sinY;
    const z1 = -p.x * sinY + p.z * cosY;
    const y1 = p.y;

    const cosX = Math.cos(rx);
    const sinX = Math.sin(rx);
    const y2 = y1 * cosX - z1 * sinX;
    const z2 = y1 * sinX + z1 * cosX;
    const x2 = x1;

    return { x: x2, y: y2, z: z2 };
  }

  checkHover(mx, my) {
    const tooltip = document.getElementById('globeNodeTooltip');
    let found = null;
    const currentRadius = this.radius * this.zoom;

    for (let i = 0; i < this.clusters.length; i++) {
      const c = this.clusters[i];
      const p3d = this.latLonTo3D(c.lat, c.lon, currentRadius);
      const rot = this.rotate3D(p3d, this.rotX, this.rotY);
      if (rot.z > -10) {
        const screenX = this.centerX + rot.x;
        const screenY = this.centerY + rot.y;
        const dist = Math.hypot(mx - screenX, my - screenY);
        if (dist < 18) {
          found = { cluster: c, screenX, screenY };
          break;
        }
      }
    }

    this.hoveredNode = found ? found.cluster : null;

    if (found) {
      this.canvas.style.cursor = 'pointer';
      this.showTooltip(found.cluster, found.screenX, found.screenY);
    } else {
      this.canvas.style.cursor = this.isDragging ? 'grabbing' : 'grab';
      if (tooltip && !tooltip.matches(':hover')) {
        tooltip.classList.remove('visible');
      }
    }
  }

  showTooltip(cluster, clientX, clientY) {
    const tooltip = document.getElementById('globeNodeTooltip');
    if (!tooltip) return;

    document.getElementById('tooltipCluster').textContent = cluster.name;
    const statusEl = document.getElementById('tooltipStatus');
    statusEl.textContent = cluster.status === 'critical' ? 'P1 Active' : 'Operational';
    statusEl.className = 'tooltip-badge ' + (cluster.status === 'critical' ? 'badge-crit' : 'badge-ok');

    document.getElementById('tooltipRegion').textContent = cluster.region;
    document.getElementById('tooltipPods').textContent = cluster.pods;
    document.getElementById('tooltipLatency').textContent = cluster.latency;

    const container = this.canvas.parentElement;
    const cRect = container.getBoundingClientRect();

    let posX = clientX + 16;
    let posY = clientY - 30;

    if (posX + 250 > cRect.width) posX = clientX - 260;
    if (posY + 160 > cRect.height) posY = clientY - 140;

    tooltip.style.left = `${posX}px`;
    tooltip.style.top = `${posY}px`;
    tooltip.classList.add('visible');
  }

  render() {
    const ctx = this.ctx;
    if (!ctx) return;

    ctx.clearRect(0, 0, this.displayWidth, this.displayHeight);

    if (this.autoRotate && !this.isDragging) {
      this.targetRotY += this.rotationSpeed;
    }
    this.rotX += (this.targetRotX - this.rotX) * 0.1;
    this.rotY += (this.targetRotY - this.rotY) * 0.1;
    this.zoom += (this.targetZoom - this.zoom) * 0.1;

    const currentRadius = this.radius * this.zoom;
    const cx = this.centerX;
    const cy = this.centerY;

    // 1. Soft Cyan/Blue Outer Halo
    const haloGradient = ctx.createRadialGradient(cx, cy, currentRadius * 0.7, cx, cy, currentRadius * 1.3);
    haloGradient.addColorStop(0, 'rgba(56, 189, 248, 0.08)');
    haloGradient.addColorStop(0.6, 'rgba(37, 99, 235, 0.04)');
    haloGradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = haloGradient;
    ctx.beginPath();
    ctx.arc(cx, cy, currentRadius * 1.3, 0, Math.PI * 2);
    ctx.fill();

    // 2. Deep Navy Glass Sphere Core
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, currentRadius, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(8, 12, 22, 0.85)';
    ctx.fill();
    ctx.lineWidth = 1.2;
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.3)';
    ctx.shadowColor = 'rgba(56, 189, 248, 0.4)';
    ctx.shadowBlur = 12;
    ctx.stroke();
    ctx.restore();

    // 3. Latitude & Longitude Thin Lines
    ctx.save();
    ctx.lineWidth = 0.7;
    [-40, 0, 40].forEach(lat => {
      ctx.beginPath();
      let first = true;
      for (let lon = -180; lon <= 180; lon += 8) {
        const p = this.latLonTo3D(lat, lon, currentRadius);
        const rot = this.rotate3D(p, this.rotX, this.rotY);
        if (rot.z > 0) {
          const sx = cx + rot.x;
          const sy = cy + rot.y;
          if (first) { ctx.moveTo(sx, sy); first = false; }
          else { ctx.lineTo(sx, sy); }
        } else {
          first = true;
        }
      }
      ctx.strokeStyle = lat === 0 ? 'rgba(56, 189, 248, 0.22)' : 'rgba(56, 189, 248, 0.08)';
      ctx.stroke();
    });
    ctx.restore();

    // 4. Glowing Cyan Continent Particles
    for (let i = 0; i < this.dots.length; i++) {
      const dot = this.dots[i];
      const p = { x: dot.x * currentRadius, y: dot.y * currentRadius, z: dot.z * currentRadius };
      const rot = this.rotate3D(p, this.rotX, this.rotY);

      if (rot.z > -10) {
        const depthAlpha = Math.max(0.1, (rot.z + currentRadius * 0.2) / (currentRadius * 1.2));
        const alpha = dot.alpha * depthAlpha;
        const sx = cx + rot.x;
        const sy = cy + rot.y;

        ctx.fillStyle = `rgba(56, 189, 248, ${alpha * 0.85})`;
        ctx.beginPath();
        ctx.arc(sx, sy, dot.size * this.zoom, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // 5. Flight Arcs
    this.renderArcs(cx, cy, currentRadius);

    // 6. Cluster Beacon Nodes
    this.renderClusterNodes(cx, cy, currentRadius);

    requestAnimationFrame(this.render);
  }

  renderArcs(cx, cy, currentRadius) {
    const ctx = this.ctx;

    for (let i = 0; i < this.arcs.length; i++) {
      const arc = this.arcs[i];
      const c1 = this.clusters[arc.from];
      const c2 = this.clusters[arc.to];

      const p1_3d = this.latLonTo3D(c1.lat, c1.lon, currentRadius);
      const p2_3d = this.latLonTo3D(c2.lat, c2.lon, currentRadius);

      const r1 = this.rotate3D(p1_3d, this.rotX, this.rotY);
      const r2 = this.rotate3D(p2_3d, this.rotX, this.rotY);

      const midLat = (c1.lat + c2.lat) / 2;
      const midLon = (c1.lon + c2.lon) / 2;
      const elevation = currentRadius * 1.25;
      const pMid_3d = this.latLonTo3D(midLat, midLon, elevation);
      const rMid = this.rotate3D(pMid_3d, this.rotX, this.rotY);

      if (r1.z > -40 || r2.z > -40) {
        const sx1 = cx + r1.x;
        const sy1 = cy + r1.y;
        const sx2 = cx + r2.x;
        const sy2 = cy + r2.y;
        const sxMid = cx + rMid.x;
        const syMid = cy + rMid.y;

        ctx.save();
        ctx.beginPath();
        ctx.moveTo(sx1, sy1);
        ctx.quadraticCurveTo(sxMid, syMid, sx2, sy2);
        ctx.strokeStyle = (c1.status === 'critical' || c2.status === 'critical')
          ? 'rgba(244, 63, 94, 0.4)'
          : 'rgba(56, 189, 248, 0.25)';
        ctx.lineWidth = 1.2;
        ctx.setLineDash([3, 4]);
        ctx.stroke();
        ctx.restore();

        // Traveling Light Packet
        arc.packets.forEach((t, pIdx) => {
          arc.packets[pIdx] = (t + arc.speed) % 1;
          const curT = arc.packets[pIdx];

          const qx = (1 - curT) * (1 - curT) * sx1 + 2 * (1 - curT) * curT * sxMid + curT * curT * sx2;
          const qy = (1 - curT) * (1 - curT) * sy1 + 2 * (1 - curT) * curT * syMid + curT * curT * sy2;

          ctx.save();
          ctx.beginPath();
          ctx.arc(qx, qy, 2.5, 0, Math.PI * 2);
          ctx.fillStyle = (c1.status === 'critical' || c2.status === 'critical') ? '#fb7185' : '#38bdf8';
          ctx.shadowColor = ctx.fillStyle;
          ctx.shadowBlur = 8;
          ctx.fill();
          ctx.restore();
        });
      }
    }
  }

  renderClusterNodes(cx, cy, currentRadius) {
    const ctx = this.ctx;

    for (let i = 0; i < this.clusters.length; i++) {
      const c = this.clusters[i];
      const p3d = this.latLonTo3D(c.lat, c.lon, currentRadius);
      const rot = this.rotate3D(p3d, this.rotX, this.rotY);

      if (rot.z > -20) {
        const sx = cx + rot.x;
        const sy = cy + rot.y;
        c.pulse = (c.pulse + 0.04) % (Math.PI * 2);

        ctx.save();

        if (c.status === 'critical') {
          const pulseSize = 8 + Math.sin(c.pulse) * 6;
          ctx.beginPath();
          ctx.arc(sx, sy, pulseSize, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(244, 63, 94, ${0.6 - Math.sin(c.pulse) * 0.3})`;
          ctx.lineWidth = 1.2;
          ctx.stroke();
        }

        ctx.beginPath();
        ctx.arc(sx, sy, c.status === 'critical' ? 5 : 4, 0, Math.PI * 2);
        ctx.fillStyle = c.color;
        ctx.shadowColor = c.color;
        ctx.shadowBlur = 12;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(sx, sy, 1.5, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.fill();

        ctx.font = '600 10px "Plus Jakarta Sans", sans-serif';
        ctx.fillStyle = '#e2e8f0';
        ctx.shadowBlur = 0;
        ctx.fillText(c.name.split('-')[0].toUpperCase(), sx + 8, sy + 3);

        ctx.restore();
      }
    }
  }
}

window.HoloGlobeEngine = HoloGlobeEngine;
