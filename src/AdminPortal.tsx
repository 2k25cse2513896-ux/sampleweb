import { FormEvent, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Product } from "./api";

type Draft = {
  id?: number;
  sku: string;
  name: string;
  slug: string;
  description: string;
  category_id: number;
  brand_id: number;
  price: number;
  mrp: number;
  cost_price: number;
  warranty_months: number;
  low_stock_threshold: number;
  stockChange: number;
  is_active: boolean;
  is_featured: boolean;
  is_genuine_verified: boolean;
};

const emptyDraft: Draft = {
  sku: "",
  name: "",
  slug: "",
  description: "",
  category_id: 0,
  brand_id: 0,
  price: 0,
  mrp: 0,
  cost_price: 0,
  warranty_months: 6,
  low_stock_threshold: 3,
  stockChange: 0,
  is_active: true,
  is_featured: false,
  is_genuine_verified: true,
};

function draftFromProduct(product: Product): Draft {
  return {
    id: product.id,
    sku: product.sku,
    name: product.name,
    slug: product.slug,
    description: product.description,
    category_id: product.category_id || 0,
    brand_id: product.brand_id || 0,
    price: product.price,
    mrp: product.mrp,
    cost_price: product.cost_price || product.price,
    warranty_months: product.warranty_months,
    low_stock_threshold: product.low_stock_threshold || 3,
    stockChange: 0,
    is_active: product.is_active,
    is_featured: product.is_featured,
    is_genuine_verified: product.is_genuine_verified,
  };
}

function AiQuickAdd({ onCreated }: { onCreated: (product: Product) => void }) {
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFeedback("");
    setError("");
    try {
      const product = await api.adminCreateFromPrompt(prompt);
      onCreated(product);
      setPrompt("");
      setFeedback(`${product.name} added with ${product.stock_qty} units in stock.`);
    } catch (value) {
      setError(value instanceof Error ? value.message : "Could not understand that product prompt.");
    } finally {
      setBusy(false);
    }
  }

  return <form className="admin-panel ai-quick-add" onSubmit={submit}><div><p className="eyebrow">Local AI quick add</p><h2>Add from a short prompt</h2><p className="admin-subtitle">Try: <code>boAt Airdopes 141 earbuds price 999 mrp 1499 stock 20</code></p></div><div className="ai-prompt-row"><textarea className="ai-prompt" required minLength={8} maxLength={500} value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Example: Sony headphones price 2499 mrp 3499 stock 8"/><button className="button primary" disabled={busy}>{busy ? "Adding…" : "Add product"}</button></div>{feedback && <div className="notice success-notice">{feedback}</div>}{error && <div className="notice error">{error}</div>}<small className="admin-hint">Offline automation: brand, category, price, MRP and stock are validated before saving.</small></form>;
}

function AdminOverview() {
  const queryClient = useQueryClient();
  const dashboard = useQuery({ queryKey: ["admin-dashboard"], queryFn: api.adminDashboard });
  const orders = useQuery({ queryKey: ["admin-orders"], queryFn: api.adminOrders });
  return <><div className="metrics"><div><small>All sales</small><strong>₹{(dashboard.data?.sales || 0).toLocaleString("en-IN")}</strong></div><div><small>Today</small><strong>₹{(dashboard.data?.today_sales || 0).toLocaleString("en-IN")}</strong></div><div><small>Orders</small><strong>{dashboard.data?.orders || 0}</strong></div><div><small>Low stock</small><strong>{dashboard.data?.low_stock.length || 0}</strong></div></div><div className="admin-grid admin-overview"><div className="admin-panel"><div className="section-heading"><h2>Latest orders</h2><span>Live queue</span></div>{orders.data?.slice(0, 8).map((order) => <div className="admin-order" key={order.order_no}><div><strong>{order.order_no}</strong><small>{order.payment_status} · ₹{order.total.toLocaleString("en-IN")}</small></div><select value={order.status} onChange={async (event) => { await api.adminStatus(order.order_no, event.target.value); await queryClient.invalidateQueries({ queryKey: ["admin-orders"] }); }}><option>new</option><option>confirmed</option><option>packed</option><option>ready_for_pickup</option><option>out_for_delivery</option><option>delivered</option><option>cancelled</option></select></div>)}</div><div className="admin-panel"><div className="section-heading"><h2>Low-stock watch</h2></div>{dashboard.data?.low_stock.map((item) => <div className="stock-row" key={item.name}><span>{item.name}</span><b>{item.stock_qty}</b></div>)}</div></div></>;
}

export default function AdminPortal() {
  const queryClient = useQueryClient();
  const [loggedIn, setLoggedIn] = useState(false);
  const [credentials, setCredentials] = useState({ email: "admin@demo.shop", password: "Admin@123" });
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [search, setSearch] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const products = useQuery({ queryKey: ["admin-products"], queryFn: () => api.products("page_size=100"), enabled: loggedIn });
  const categories = useQuery({ queryKey: ["admin-categories"], queryFn: api.categories, enabled: loggedIn });
  const brands = useQuery({ queryKey: ["admin-brands"], queryFn: api.brands, enabled: loggedIn });
  const filteredProducts = useMemo(() => products.data?.items.filter((product) => `${product.name} ${product.sku}`.toLowerCase().includes(search.toLowerCase())) || [], [products.data, search]);

  async function signIn(event: FormEvent) {
    event.preventDefault();
    try {
      const result = await api.login(credentials);
      localStorage.setItem("tech-toys-token", result.access_token);
      setLoggedIn(true);
      setError("");
    } catch (value) {
      setError(value instanceof Error ? value.message : "Could not sign in.");
    }
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    setError("");
    try {
      const body = {
        sku: draft.sku,
        name: draft.name,
        slug: draft.slug,
        description: draft.description,
        category_id: Number(draft.category_id),
        brand_id: Number(draft.brand_id),
        price: Number(draft.price),
        mrp: Number(draft.mrp),
        cost_price: Number(draft.cost_price),
        warranty_months: Number(draft.warranty_months),
        low_stock_threshold: Number(draft.low_stock_threshold),
        is_active: draft.is_active,
        is_featured: draft.is_featured,
        is_genuine_verified: draft.is_genuine_verified,
        specs_json: "{}",
        ...(draft.id ? {} : { stock_qty: 0 }),
      };
      const saved = draft.id ? await api.adminUpdateProduct(draft.id, body) : await api.adminCreateProduct(body);
      if (draft.stockChange !== 0) await api.adminStock({ product_id: saved.id, change_qty: Number(draft.stockChange), reason: "admin_portal" });
      if (image) await api.adminUploadImage(saved.id, image);
      await queryClient.invalidateQueries({ queryKey: ["admin-products"] });
      setDraft(draftFromProduct(saved));
      setImage(null);
      setMessage(draft.id ? "Product updated successfully." : "Product created successfully.");
    } catch (value) {
      setError(value instanceof Error ? value.message : "Could not save product.");
    }
  }

  async function removeProduct() {
    if (!draft.id || !window.confirm(`Deactivate ${draft.name}? It will be hidden from the shop but kept for order history.`)) return;
    setMessage("");
    setError("");
    try {
      await api.adminDeleteProduct(draft.id);
      await queryClient.invalidateQueries({ queryKey: ["admin-products"] });
      setDraft(emptyDraft);
      setImage(null);
      setMessage("Product deactivated and hidden from the shop.");
    } catch (value) {
      setError(value instanceof Error ? value.message : "Could not deactivate product.");
    }
  }

  if (!loggedIn) return <section className="section page-section narrow-page"><form className="admin-login" onSubmit={signIn}><p className="eyebrow">Staff portal</p><h1>Manage your catalogue.</h1><p>Sign in to update real products, prices, stock and photos.</p><label>Email<input type="email" value={credentials.email} onChange={(event) => setCredentials({ ...credentials, email: event.target.value })}/></label><label>Password<input type="password" value={credentials.password} onChange={(event) => setCredentials({ ...credentials, password: event.target.value })}/></label>{error && <div className="notice error">{error}</div>}<button className="button primary full">Sign in</button><small className="admin-hint">Local owner login: admin@demo.shop / Admin@123</small></form></section>;

  return <section className="section page-section"><div className="admin-head"><div><p className="eyebrow">Staff portal</p><h1>Manage your catalogue.</h1><p className="admin-subtitle">Update the products customers see in the shop.</p></div><button className="button ghost" onClick={() => { localStorage.removeItem("tech-toys-token"); setLoggedIn(false); }}>Sign out</button></div><AdminOverview /><AiQuickAdd onCreated={(product) => { setDraft(draftFromProduct(product)); setImage(null); setMessage("Product created from prompt."); setError(""); queryClient.invalidateQueries({ queryKey: ["admin-products"] }); }} /><div className="admin-product-layout"><aside className="admin-panel inventory-panel"><div className="section-heading"><h2>Inventory</h2><button className="button primary" onClick={() => { setDraft(emptyDraft); setImage(null); setMessage(""); setError(""); }}>New product</button></div><input className="admin-search" placeholder="Search products or SKU" value={search} onChange={(event) => setSearch(event.target.value)}/><div className="admin-product-list">{products.isLoading && <p>Loading catalogue…</p>}{filteredProducts.map((product) => <button className={`admin-product-row ${draft.id === product.id ? "selected" : ""}`} key={product.id} onClick={() => { setDraft(draftFromProduct(product)); setImage(null); setMessage(""); setError(""); }}><span><strong>{product.name}</strong><small>{product.sku} · {product.category_name || "Product"}</small></span><b>₹{product.price.toLocaleString("en-IN")}<small>{product.stock_qty} in stock</small></b></button>)}</div></aside><form className="admin-panel admin-product-form" onSubmit={save}><div className="section-heading"><div><p className="eyebrow">Product editor</p><h2>{draft.id ? "Edit product" : "Add product"}</h2></div>{draft.id && <span className="admin-id">ID #{draft.id}</span>}</div><div className="admin-form-grid"><label>Product name<input required value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })}/></label><label>SKU<input required value={draft.sku} onChange={(event) => setDraft({ ...draft, sku: event.target.value })}/></label><label>URL slug<input required value={draft.slug} onChange={(event) => setDraft({ ...draft, slug: event.target.value })}/></label><label>Category<select required value={draft.category_id} onChange={(event) => setDraft({ ...draft, category_id: Number(event.target.value) })}><option value={0} disabled>Select category</option>{categories.data?.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label>Brand<select required value={draft.brand_id} onChange={(event) => setDraft({ ...draft, brand_id: Number(event.target.value) })}><option value={0} disabled>Select brand</option>{brands.data?.map((brand) => <option key={brand.id} value={brand.id}>{brand.name}</option>)}</select></label><label>Price (₹)<input required type="number" min={0} value={draft.price} onChange={(event) => setDraft({ ...draft, price: Number(event.target.value) })}/></label><label>MRP (₹)<input required type="number" min={0} value={draft.mrp} onChange={(event) => setDraft({ ...draft, mrp: Number(event.target.value) })}/></label><label>Cost price (₹)<input required type="number" min={0} value={draft.cost_price} onChange={(event) => setDraft({ ...draft, cost_price: Number(event.target.value) })}/></label><label>Stock adjustment<input type="number" value={draft.stockChange} onChange={(event) => setDraft({ ...draft, stockChange: Number(event.target.value) })}/><small>Use +10 to restock or -2 to reduce.</small></label><label>Warranty (months)<input type="number" min={0} value={draft.warranty_months} onChange={(event) => setDraft({ ...draft, warranty_months: Number(event.target.value) })}/></label></div><label>Description<textarea value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })}/></label><label className="file-field">Product photo<input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => setImage(event.target.files?.[0] || null)}/><small>{image ? image.name : "Choose a JPG, PNG or WebP image"}</small></label><div className="admin-checks"><label><input type="checkbox" checked={draft.is_active} onChange={(event) => setDraft({ ...draft, is_active: event.target.checked })}/> Visible in shop</label><label><input type="checkbox" checked={draft.is_featured} onChange={(event) => setDraft({ ...draft, is_featured: event.target.checked })}/> Featured</label><label><input type="checkbox" checked={draft.is_genuine_verified} onChange={(event) => setDraft({ ...draft, is_genuine_verified: event.target.checked })}/> Genuine verified</label></div>{message && <div className="notice success-notice">{message}</div>}{error && <div className="notice error">{error}</div>}<div className="admin-form-actions">{draft.id && <button type="button" className="button danger-button" onClick={removeProduct}>Deactivate product</button>}<button className="button primary full">{draft.id ? "Save product changes" : "Create product"}</button></div></form></div></section>;
}
