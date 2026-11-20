export interface OtpChallenge {
  message: string
  phone_number: string
  demo_otp: string
  is_new_user: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  profile_completed: boolean
  role: UserRole
}

export type UserRole = 'CUSTOMER' | 'SHOP_OWNER' | 'ADMIN'

export interface UserProfile {
  id: number
  phone_number: string
  full_name: string
  email: string | null
  role: UserRole
  phone_verified: boolean
  profile_completed: boolean
  coffee_preferences: string[]
  allergens: string[]
}

export interface FavoriteOrderResponse {
  order_id: number
  is_favorite: boolean
}

export interface AdminUser {
  id: number
  username: string | null
  phone_number: string | null
  full_name: string
  email: string | null
  role: UserRole
  phone_verified: boolean
  profile_completed: boolean
}

export interface AdminShop {
  id: number
  name: string
  address: string
  latitude: number
  longitude: number
  opening_hours: string | null
  rating: number | null
  rating_count: number
  owner_id: number | null
  owner_name: string | null
}

export interface AdminShopPayload {
  name: string
  address: string
  latitude: number
  longitude: number
  opening_hours: string | null
  owner_id: number | null
}

export interface GeocodeResult {
  latitude: number
  longitude: number
  display_name: string
}

export type CoffeeSize = 'S' | 'M' | 'L'

export type MilkType = 'NONE' | 'WHOLE' | 'OAT' | 'ALMOND' | 'LACTOSE_FREE'

export interface Product {
  id: number
  name: string
  description: string | null
  category: string
  price: string | number
  size_price_deltas: Record<CoffeeSize, string | number>
  milk_price_deltas: Record<MilkType, string | number>
  extra_shot_price: string | number
  is_available: boolean
}

export interface ProductUpsertPayload {
  name: string
  description: string | null
  category: string
  price: string
  size_price_deltas: Record<CoffeeSize, string>
  milk_price_deltas: Record<MilkType, string>
  extra_shot_price: string
}

export interface Coordinates {
  latitude: number
  longitude: number
}

export interface Shop {
  id: number
  name: string
  address: string
  latitude: number
  longitude: number
  opening_hours: string | null
  rating: number | null
  rating_count: number
  distance_km: number | null
}

export interface ShopDetail extends Shop {
  products: Product[]
}

export interface MyShopRating {
  rating: number | null
}

export interface ShopRatingResult {
  user_rating: number
  average_rating: number
  rating_count: number
}

export interface OrderCustomizations {
  size: CoffeeSize
  sugar_level: number
  milk_type: MilkType
  extra_shots: number
}

export interface QrCodePayload {
  order_id: string
  user_id: string
  shop_id: string
  created_at: string
  signature: string
}

export interface Order {
  id: number
  shop_id: number
  shop_name: string
  customer_name: string
  customer_phone: string
  product_id: number
  product_name: string
  quantity: number
  unit_price: string | number
  customizations: OrderCustomizations
  status: 'PENDING' | 'ACCEPTED' | 'PREPARING' | 'READY' | 'DELIVERED'
  qr_code: QrCodePayload | null
  created_at: string
}

export interface QrVerificationResponse {
  valid: boolean
  order_id: string | null
  status: Order['status'] | null
  message: string
}

export interface Plan {
  id: number
  code: string
  name: string
  monthly_price: string | number
  monthly_credits: number | null
  guest_credits: number
  priority_pickup: boolean
}

export interface Subscription {
  id: number
  plan_code: string
  plan_name: string
  status: string
  remaining_credits: number | null
  started_at: string
  expires_at: string
  guest_credits: number
  priority_pickup: boolean
}

export interface PurchaseResponse {
  success: boolean
  message: string
  payment_status: string
  subscription: Subscription | null
}

export interface CancellationResponse {
  status: string
  message: string
}
