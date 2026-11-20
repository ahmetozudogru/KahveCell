import { useState, type FormEvent } from 'react'

import { useToast } from '../app/useToast'
import { apiRequest } from '../lib/api'
import type {
  CoffeeSize,
  MilkType,
  Product,
  ProductUpsertPayload,
} from '../types/api'

interface ShopMenuEditorProps {
  shopId: number
  products: Product[]
  onProductChange: (product: Product) => void
}

interface ProductDraft {
  name: string
  description: string
  category: string
  price: string
  size_price_deltas: Record<CoffeeSize, string>
  milk_price_deltas: Record<MilkType, string>
  extra_shot_price: string
}

const COFFEE_SIZES: CoffeeSize[] = ['S', 'M', 'L']
const MILK_TYPES: Array<{ value: MilkType; label: string }> = [
  { value: 'NONE', label: 'Sütsüz' },
  { value: 'WHOLE', label: 'Normal süt' },
  { value: 'OAT', label: 'Yulaf sütü' },
  { value: 'ALMOND', label: 'Badem sütü' },
  { value: 'LACTOSE_FREE', label: 'Laktozsuz süt' },
]

function createEmptyDraft(): ProductDraft {
  return {
    name: '',
    description: '',
    category: 'Espresso Bazlı',
    price: '',
    size_price_deltas: { S: '0.00', M: '0.00', L: '0.00' },
    milk_price_deltas: {
      NONE: '0.00',
      WHOLE: '0.00',
      OAT: '0.00',
      ALMOND: '0.00',
      LACTOSE_FREE: '0.00',
    },
    extra_shot_price: '0.00',
  }
}

function draftFromProduct(product: Product): ProductDraft {
  return {
    name: product.name,
    description: product.description ?? '',
    category: product.category,
    price: String(product.price),
    size_price_deltas: {
      S: String(product.size_price_deltas.S),
      M: String(product.size_price_deltas.M),
      L: String(product.size_price_deltas.L),
    },
    milk_price_deltas: {
      NONE: String(product.milk_price_deltas.NONE),
      WHOLE: String(product.milk_price_deltas.WHOLE),
      OAT: String(product.milk_price_deltas.OAT),
      ALMOND: String(product.milk_price_deltas.ALMOND),
      LACTOSE_FREE: String(product.milk_price_deltas.LACTOSE_FREE),
    },
    extra_shot_price: String(product.extra_shot_price),
  }
}

function formatPrice(value: string | number): string {
  return new Intl.NumberFormat('tr-TR', {
    style: 'currency',
    currency: 'TRY',
  }).format(Number(value))
}

function formatDelta(value: string | number): string {
  const amount = Number(value)
  if (amount === 0) {
    return 'Fiyata dahil'
  }
  const absoluteAmount = formatPrice(Math.abs(amount))
  return amount > 0 ? `+${absoluteAmount}` : `−${absoluteAmount}`
}

export function ShopMenuEditor({
  shopId,
  products,
  onProductChange,
}: ShopMenuEditorProps) {
  const [formOpen, setFormOpen] = useState(false)
  const [editingProductId, setEditingProductId] = useState<number | null>(null)
  const [draft, setDraft] = useState<ProductDraft>(createEmptyDraft)
  const [saving, setSaving] = useState(false)
  const [busyProductId, setBusyProductId] = useState<number | null>(null)
  const { notify } = useToast()

  function beginCreate() {
    setEditingProductId(null)
    setDraft(createEmptyDraft())
    setFormOpen(true)
  }

  function beginEdit(product: Product) {
    setEditingProductId(product.id)
    setDraft(draftFromProduct(product))
    setFormOpen(true)
  }

  function closeForm() {
    setFormOpen(false)
    setEditingProductId(null)
    setDraft(createEmptyDraft())
  }

  async function saveProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)

    const payload: ProductUpsertPayload = {
      ...draft,
      description: draft.description.trim() || null,
    }
    const isEditing = editingProductId !== null
    const path = `/shops/${shopId}/products${
      isEditing ? `/${editingProductId}` : ''
    }`

    try {
      const product = await apiRequest<Product>(path, {
        method: isEditing ? 'PUT' : 'POST',
        body: JSON.stringify(payload),
      })
      onProductChange(product)
      closeForm()
      notify(
        isEditing ? 'Ürün bilgileri güncellendi.' : 'Ürün menüye eklendi.',
        'success',
      )
    } catch (requestError) {
      notify(
        requestError instanceof Error
          ? requestError.message
          : 'Ürün kaydedilemedi.',
        'error',
      )
    } finally {
      setSaving(false)
    }
  }

  async function toggleAvailability(product: Product) {
    setBusyProductId(product.id)
    try {
      const updatedProduct = product.is_available
        ? await apiRequest<Product>(
            `/shops/${shopId}/products/${product.id}`,
            { method: 'DELETE' },
          )
        : await apiRequest<Product>(
            `/shops/${shopId}/products/${product.id}/availability`,
            {
              method: 'PATCH',
              body: JSON.stringify({ is_available: true }),
            },
          )
      onProductChange(updatedProduct)
      notify(
        updatedProduct.is_available
          ? 'Ürün tekrar menüye eklendi.'
          : 'Ürün menüden çıkarıldı.',
        'success',
      )
    } catch (requestError) {
      notify(
        requestError instanceof Error
          ? requestError.message
          : 'Ürünün durumu güncellenemedi.',
        'error',
      )
    } finally {
      setBusyProductId(null)
    }
  }

  function setSizeDelta(size: CoffeeSize, value: string) {
    setDraft((current) => ({
      ...current,
      size_price_deltas: {
        ...current.size_price_deltas,
        [size]: value,
      },
    }))
  }

  function setMilkDelta(milkType: MilkType, value: string) {
    setDraft((current) => ({
      ...current,
      milk_price_deltas: {
        ...current.milk_price_deltas,
        [milkType]: value,
      },
    }))
  }

  return (
    <section className="owner-shop-menu menu-editor">
      <div className="menu-editor-heading">
        <h3>Menü ve fiyatlar</h3>
      </div>
      <p className="menu-pricing-note" role="note">
        Temel fiyat M boy, normal süt ve ekstra shotsız seçeneğe aittir. Boyut,
        süt ve shot tercihleri toplam fiyatı değiştirebilir.
      </p>
      {!formOpen && (
        <div className="menu-add-action">
          <button onClick={beginCreate} type="button">
            Ürün ekle
          </button>
        </div>
      )}

      {products.length === 0 ? (
        <p className="muted">
          Menünüz boş. İlk ürününüzü ekleyerek başlayın.
        </p>
      ) : (
        <ul className="menu-product-list">
          {products.map((product) => (
            <li className="menu-product-row" key={product.id}>
              <div className="menu-product-info">
                <strong>{product.name}</strong>
                <small>
                  {product.category}
                  {!product.is_available && ' · Menüden çıkarıldı'}
                </small>
                <span className="menu-base-price">
                  Temel fiyat: {formatPrice(product.price)}
                </span>
                <details>
                  <summary>Fiyat farklarını gör</summary>
                  <small>
                    Boyut: S {formatDelta(product.size_price_deltas.S)} · M{' '}
                    {formatDelta(product.size_price_deltas.M)} · L{' '}
                    {formatDelta(product.size_price_deltas.L)}
                  </small>
                  <small>
                    Süt:{' '}
                    {MILK_TYPES.map(
                      ({ value, label }) =>
                        `${label} ${formatDelta(product.milk_price_deltas[value])}`,
                    ).join(' · ')}
                  </small>
                  <small>
                    Ekstra shot: {formatPrice(product.extra_shot_price)} / adet
                  </small>
                </details>
              </div>
              <div className="menu-product-actions">
                <button
                  className="secondary-button"
                  disabled={saving || busyProductId !== null}
                  onClick={() => beginEdit(product)}
                  type="button"
                >
                  Düzenle
                </button>
                <button
                  className={
                    product.is_available
                      ? 'danger-button'
                      : 'secondary-button'
                  }
                  disabled={saving || busyProductId !== null}
                  onClick={() => void toggleAvailability(product)}
                  type="button"
                >
                  {busyProductId === product.id
                    ? 'Güncelleniyor…'
                    : product.is_available
                      ? 'Menüden çıkar'
                      : 'Menüye ekle'}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {formOpen && (
        <form className="panel stack menu-product-form" onSubmit={saveProduct}>
          <h4>{editingProductId === null ? 'Yeni ürün' : 'Ürünü düzenle'}</h4>
          <div className="menu-product-fields">
            <label>
              Ürün adı
              <input
                maxLength={120}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    name: event.target.value,
                  }))
                }
                required
                value={draft.name}
              />
            </label>
            <label>
              Kategori
              <select
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    category: event.target.value,
                  }))
                }
                value={draft.category}
              >
                <option value="Espresso Bazlı">Espresso Bazlı</option>
                <option value="Filtre Kahveler">Filtre Kahveler</option>
                <option value="Soğuk İçecekler">Soğuk İçecekler</option>
                <option value="Diğer">Diğer</option>
                <option value="COFFEE">Kahve (mevcut kategori)</option>
              </select>
            </label>
            <label>
              Temel fiyat (TL)
              <input
                min="0.01"
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    price: event.target.value,
                  }))
                }
                required
                step="0.01"
                type="number"
                value={draft.price}
              />
            </label>
            <label>
              Açıklama
              <textarea
                maxLength={1000}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    description: event.target.value,
                  }))
                }
                rows={2}
                value={draft.description}
              />
            </label>
          </div>

          <fieldset className="menu-price-fieldset">
            <legend>Boyuta göre fiyat farkı (TL)</legend>
            <div className="price-adjustment-grid">
              {COFFEE_SIZES.map((size) => (
                <label key={size}>
                  {size} boy
                  <input
                    onChange={(event) => setSizeDelta(size, event.target.value)}
                    step="0.01"
                    type="number"
                    value={draft.size_price_deltas[size]}
                  />
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset className="menu-price-fieldset">
            <legend>Süt tipine göre fiyat farkı (TL)</legend>
            <div className="price-adjustment-grid">
              {MILK_TYPES.map(({ value, label }) => (
                <label key={value}>
                  {label}
                  <input
                    onChange={(event) =>
                      setMilkDelta(value, event.target.value)
                    }
                    step="0.01"
                    type="number"
                    value={draft.milk_price_deltas[value]}
                  />
                </label>
              ))}
            </div>
          </fieldset>

          <label>
            Ekstra shot ücreti (TL / shot)
            <input
              min="0"
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  extra_shot_price: event.target.value,
                }))
              }
              step="0.01"
              type="number"
              value={draft.extra_shot_price}
            />
          </label>

          <div className="menu-product-actions">
            <button disabled={saving} type="submit">
              {saving ? 'Kaydediliyor…' : 'Kaydet'}
            </button>
            <button
              className="secondary-button"
              disabled={saving}
              onClick={closeForm}
              type="button"
            >
              Vazgeç
            </button>
          </div>
        </form>
      )}
    </section>
  )
}
