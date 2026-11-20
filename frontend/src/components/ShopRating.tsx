interface ShopRatingProps {
  rating: number | null
  ratingCount: number
}

function formatRatingCount(count: number): string {
  if (count < 50) {
    return String(count)
  }
  return `${Math.floor(count / 50) * 50}+`
}

export function ShopRating({ rating, ratingCount }: ShopRatingProps) {
  const exactCount = `${ratingCount.toLocaleString('tr-TR')} değerlendirme`

  return (
    <span
      aria-label={
        rating === null
          ? `Henüz puanlanmadı, ${exactCount}`
          : `Puan ${rating.toFixed(1)}, ${exactCount}`
      }
      className="shop-rating"
    >
      {rating === null ? 'Henüz puanlanmadı' : `★ ${rating.toFixed(1)}`}
      <span className="shop-rating-count" title={exactCount}>
        {formatRatingCount(ratingCount)}
      </span>
    </span>
  )
}
