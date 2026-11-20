import { Link } from 'react-router-dom'

export function LandingPage() {
  return (
    <div className="page-stack landing-page">
      <section className="landing-hero">
        <div className="landing-copy">
          <p className="eyebrow">KahveCell'e hoş geldin</p>
          <h1>Her kahve molası, iyi hissettirsin.</h1>
          <p>
            Yakınındaki kahvecileri keşfet, içeceğini damak tadına göre
            özelleştir ve siparişini hazır olduğunda kolayca teslim al.
          </p>
          <div className="landing-actions">
            <Link className="button-link" to="/shops">
              Dükkânları keşfet
            </Link>
            <Link className="landing-secondary-link" to="/register">
              Hemen kayıt ol
            </Link>
          </div>
        </div>
        <aside className="landing-highlight">
          <span aria-hidden="true" className="landing-cup">
            ☕
          </span>
          <p className="eyebrow">Kahve molan, senin seçimin</p>
          <h2>Seç. Özelleştir. Afiyetle iç.</h2>
          <p>
            Menüleri incele, boyut ve süt tercihlerini belirle; siparişinin
            durumunu uygulamadan takip et.
          </p>
          <div className="landing-highlight-footer">
            <span>01</span>
            <span>Keşiften teslimata tek yerde</span>
          </div>
        </aside>
      </section>

      <section aria-label="KahveCell nasıl çalışır" className="landing-steps">
        <article className="panel landing-step">
          <span className="landing-step-number">01</span>
          <h2>Yakınındaki kahvecileri bul</h2>
          <p className="muted">
            Haritadan konumuna yakın dükkânları ve menülerini keşfet.
          </p>
        </article>
        <article className="panel landing-step">
          <span className="landing-step-number">02</span>
          <h2>Kahveni sana göre seç</h2>
          <p className="muted">
            Boyutunu, sütünü ve ek shot seçeneklerini belirleyerek siparişini
            özelleştir.
          </p>
        </article>
        <article className="panel landing-step">
          <span className="landing-step-number">03</span>
          <h2>Hazır olunca teslim al</h2>
          <p className="muted">
            Sipariş durumunu takip et ve hazır olduğunda QR kodunla kahveni
            teslim al.
          </p>
        </article>
      </section>

      <section className="landing-cta">
        <div>
          <p className="eyebrow">Bir sonraki molan</p>
          <h2>Güzel kahve, yakında.</h2>
        </div>
        <Link className="button-link" to="/shops">
          Kahvecileri gör
        </Link>
      </section>
    </div>
  )
}
