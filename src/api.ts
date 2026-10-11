const defaultApiUrl = import.meta.env.PROD
  ? "https://tech-toys-api.onrender.com"
  : "http://127.0.0.1:8000";

export const API_URL = import.meta.env.VITE_API_URL || defaultApiUrl;

export type Settings = Record<string, string>;

export interface Product {
  id: number; sku: string; name: string; slug: string; description: string; category_id?: number; brand_id?: number; price: number; mrp: number;
  stock_qty: number; warranty_months: number; is_featured: boolean; is_genuine_verified: boolean;
  category_name?: string; brand_name?: string; specs_json: string; images?: Array<{ id: number; url: string }>;
}

export interface Page<T> { items: T[]; total: number; page: number; page_size: number; }
export interface Order { order_no: string; status: string; payment_status: string; total: number; items: Array<{ name: string; qty: number; price: number }>; events: Array<{ status: string; note: string; created_at: string }>; }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem("tech-toys-token");
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  const body: unknown = await response.json();
  if (!response.ok) {
    const message = typeof body === "object" && body !== null && "error" in body ? String((body as { error: { message: string } }).error.message) : "Something went wrong.";
    throw new Error(message);
  }
  return body as T;
}

export const api = {
  settings: () => request<Settings>("/api/settings"),
  products: (query: string) => request<Page<Product>>(`/api/products?${query}`),
  product: (slug: string) => request<Product>(`/api/products/${slug}`),
  categories: () => request<Array<{ id: number; name: string; slug: string }>>("/api/categories"),
  brands: () => request<Array<{ id: number; name: string; slug: string }>>("/api/brands"),
  deals: () => request<Array<{ product: Product; ends_at: string }>>("/api/flash-deals"),
  phones: (q: string) => request<Array<{ id: number; brand: string; model_name: string; slug: string; connector_type: string }>>(`/api/phone-models?q=${encodeURIComponent(q)}`),
  compatible: (model: string) => request<{ phone: { model_name: string }; groups: Record<string, Product[]> }>(`/api/compatible?model=${encodeURIComponent(model)}`),
  assistant: (text: string) => request<{ reply: string; products: Product[] }>("/api/assistant", { method: "POST", body: JSON.stringify({ text }) }),
  quote: (body: unknown) => request<{ subtotal: number; discount: number; delivery_fee: number; total: number }>("/api/cart/quote", { method: "POST", body: JSON.stringify(body) }),
  login: (body: unknown) => request<{ access_token: string }>("/api/auth/admin/login", { method: "POST", body: JSON.stringify(body) }),
  otp: (body: unknown) => request<{ message: string; demo_otp?: string }>("/api/auth/customer/request-otp", { method: "POST", body: JSON.stringify(body) }),
  verifyOtp: (body: unknown) => request<{ access_token: string }>("/api/auth/customer/verify-otp", { method: "POST", body: JSON.stringify(body) }),
  order: (body: unknown) => request<Order>("/api/orders", { method: "POST", body: JSON.stringify(body) }),
  track: (orderNo: string, phone: string) => request<Order>(`/api/orders/${encodeURIComponent(orderNo)}/track?phone=${encodeURIComponent(phone)}`),
  adminDashboard: () => request<{ sales: number; today_sales: number; orders: number; status_counts: Record<string, number>; low_stock: Array<{ name: string; stock_qty: number }> }>("/api/admin/dashboard"),
  adminOrders: () => request<Array<{ order_no: string; status: string; total: number; payment_status: string }>>("/api/admin/orders"),
  adminStatus: (orderNo: string, status: string) => request<Order>(`/api/admin/orders/${encodeURIComponent(orderNo)}/status`, { method: "POST", body: JSON.stringify({ status, note: "Updated from dashboard." }) }),
  adminStock: (body: { product_id: number; change_qty: number; reason: string }) => request<{ product_id: number; stock_qty: number }>("/api/admin/stock", { method: "POST", body: JSON.stringify(body) }),
  adminCreateProduct: (body: unknown) => request<Product>("/api/admin/products", { method: "POST", body: JSON.stringify(body) }),
  adminCreateFromPrompt: (prompt: string) => request<Product>("/api/admin/products/from-prompt", { method: "POST", body: JSON.stringify({ prompt }) }),
  adminUpdateProduct: (id: number, body: unknown) => request<Product>(`/api/admin/products/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  adminDeleteProduct: (id: number) => request<{ message: string }>(`/api/admin/products/${id}`, { method: "DELETE" }),
  adminUploadImage: (id: number, file: File) => { const form = new FormData(); form.append("file", file); return request<Product>(`/api/admin/products/${id}/images`, { method: "POST", body: form }); },
};
