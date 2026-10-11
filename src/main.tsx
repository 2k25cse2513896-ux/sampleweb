import { StrictMode, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { api, type Order, type Product } from "./api";
import { useStore } from "./store";
import AdminPortal from "./AdminPortal";
import BrandLogo from "./BrandLogo";
import ProductIllustration from "./ProductIllustration";
import "./styles.css";

const money = (value: number) => `₹${value.toLocaleString("en-IN")}`;
const queryClient = new QueryClient();
const VIDEO_STORAGE_KEY = "tech-toys-bg-video";

function productCategory(product: Product): string {
  const name = product.name.toLowerCase();
  const value = `${product.specs_json || ""} ${product.category_name || ""}`.toLowerCase();
  if (name.includes("earbud")) return "Earbuds";
  if (name.includes("headphone")) return "Headphones";
  if (name.includes("neckband")) return "Neckband";
  if (name.includes("watch")) return "Smartwatch";
  if (name.includes("speaker")) return "Speaker";
  if (name.includes("power bank")) return "Power bank";
  if (name.includes("charger")) return "Charger";
  if (name.includes("cable")) return "Cable";
  if (name.includes("pendrive") || name.includes("memory")) return "Storage";
  if (name.includes("cover") || name.includes("glass") || name.includes("stand")) return "Accessories";
  if (value.includes("memory") || value.includes("pendrive")) return "Storage";
  if (value.includes("speaker")) return "Speaker";
  if (value.includes("watch")) return "Smartwatch";
  if (value.includes("earbud")) return "Earbuds";
  if (value.includes("headphone")) return "Headphones";
  if (value.includes("neckband")) return "Neckband";
  if (value.includes("power bank")) return "Power bank";
  if (value.includes("charger")) return "Charger";
  if (value.includes("cable")) return "Cable";
  if (value.includes("cover") || value.includes("glass") || value.includes("stand")) return "Accessories";
  return product.category_name || "Gadget";
}

function productSpecs(product: Product): string[] {
  if (!product.specs_json) return [];
  try {
    const parsed: unknown = JSON.parse(product.specs_json);
    if (typeof parsed !== "object" || parsed === null) return [];
    return Object.entries(parsed as Record<string, unknown>).slice(0, 3).map(([key, value]) => `${key}: ${String(value)}`);
  } catch {
    return product.specs_json.split(",").map((item) => item.trim()).filter(Boolean).slice(0, 3);
  }
}

function useIsDesktop(): boolean {
  const [desktop, setDesktop] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(min-width: 1024px) and (hover: hover) and (pointer: fine)");
    const update = () => setDesktop(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return desktop;
}

function BackgroundVideo() {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    function updatePlayback() {
      if (document.hidden) {
        video.pause();
        return;
      }
      void video.play().catch(() => undefined);
    }
    document.addEventListener("visibilitychange", updatePlayback);
    updatePlayback();
    return () => document.removeEventListener("visibilitychange", updatePlayback);
  }, []);

  function useRemoteFallback(event: React.SyntheticEvent<HTMLVideoElement>) {
    const fallback = import.meta.env.VITE_BG_VIDEO_URL;
    const video = event.currentTarget;
    if (fallback && video.src !== fallback) {
      video.src = fallback;
      video.load();
      void video.play().catch(() => undefined);
    }
  }

  return <div className="background-video" aria-hidden="true"><video ref={videoRef} autoPlay muted loop playsInline preload="metadata" poster="/favicon.svg" onError={useRemoteFallback} src="/media/bg.mp4"/><div className="background-video-overlay"/></div>;
}

function Reveal({ children }: { children: React.ReactNode }) {
  const elementRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = elementRef.current;
    if (!element) return;
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          element.classList.add("is-visible");
          observer.unobserve(element);
        }
      });
    }, { threshold: 0.12 });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return <div className="reveal" ref={elementRef}>{children}</div>;
}

function Layout({ children }: { children: React.ReactNode }) {
  const cart = useStore((state) => state.cart);
  const wishlist = useStore((state) => state.wishlist);
  const isDesktop = useIsDesktop();
  const location = useLocation();
  const isAdmin = location.pathname.startsWith("/admin");
  const [videoEnabled, setVideoEnabled] = useState(() => localStorage.getItem(VIDEO_STORAGE_KEY) !== "off");
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const name = settings.data?.shop_name || "TECH TOYS";
  function toggleVideo() {
    const next = !videoEnabled;
    setVideoEnabled(next);
    localStorage.setItem(VIDEO_STORAGE_KEY, next ? "on" : "off");
  }
  const banner = settings.data?.demo_banner || "Warranty-backed tech · Same-day Kanpur delivery · Human support";
  const cartCount = cart.reduce((sum, item) => sum + item.qty, 0);
  return <div className={`app-shell ${isAdmin ? "admin-shell" : ""}`}>
    {isDesktop && !isAdmin && videoEnabled && <BackgroundVideo/>}
    <div className="demo-banner">{banner}</div>
    <header><Link className="brand" to="/"><BrandLogo name={name}/></Link><nav><Link to="/shop">Shop</Link><Link to="/finder">Phone finder</Link><Link to="/repair">Repairs</Link><Link to="/track">Track order</Link><Link to="/admin">Staff portal</Link>{isDesktop && !isAdmin && <button className="video-toggle" onClick={toggleVideo} aria-pressed={videoEnabled}>Background video {videoEnabled ? "on" : "off"}</button>}</nav><div className="header-actions"><Link className="search-pill" to="/shop" aria-label="Search products">⌕ <span>Search products</span></Link><Link className="wishlist-pill" to="/wishlist" aria-label={`Wishlist, ${wishlist.length} saved products`}>♡ <b>{wishlist.length}</b></Link><Link className="cart-pill" to="/cart">Cart <b>{cartCount}</b></Link></div></header>
    <main>{children}</main>
    <nav className="bottom-nav"><Link to="/"><span>⌂</span>Home</Link><Link to="/shop"><span>▦</span>Categories</Link><Link to="/wishlist"><span>♡</span>Wishlist</Link><Link to="/track"><span>◷</span>Orders</Link><Link to="/admin"><span>○</span>Account</Link></nav>
    <footer><div><BrandLogo name={name} footer/><p>{settings.data?.tagline || "Gadgets that last. Advice you can trust."}</p></div><div><small>{settings.data?.address || "Sagar Market, Kanpur"}</small><br/><small>{settings.data?.timing || "10 AM to 10 PM"}</small></div><a href={`https://wa.me/${settings.data?.whatsapp || "916307001812"}`}>WhatsApp the shop ↗</a></footer>
  </div>;
}

function ProductCard({ product }: { product: Product }) {
  const add = useStore((state) => state.add);
  const requestAlert = useStore((state) => state.requestAlert);
  const toggleWishlist = useStore((state) => state.toggleWishlist);
  const wishlisted = useStore((state) => state.wishlist.some((item) => item.id === product.id));
  const alertSet = useStore((state) => state.alertIds.includes(product.id));
  const [feedback, setFeedback] = useState("");
  const category = productCategory(product);
  const specs = productSpecs(product);
  const discount = product.mrp > product.price ? Math.round(((product.mrp - product.price) * 100) / product.mrp) : 0;
  function handleAction() {
    if (product.stock_qty > 0) {
      add(product);
      setFeedback("Added to cart +1");
    } else {
      requestAlert(product.id);
      setFeedback("Stock alert set ✓");
    }
    window.setTimeout(() => setFeedback(""), 2200);
  }
  function handleWishlist(event: React.MouseEvent<HTMLButtonElement>) {
    event.preventDefault();
    event.stopPropagation();
    toggleWishlist(product);
  }
  return <article className="product-card"><div className="product-card-link"><div className="product-art"><Link to={`/product/${product.slug}`} aria-label={`View ${product.name}`}><ProductIllustration category={category}/><span>{category}</span></Link><button className={`heart-button ${wishlisted ? "is-wishlisted" : ""}`} aria-label={wishlisted ? `Remove ${product.name} from wishlist` : `Save ${product.name} to wishlist`} aria-pressed={wishlisted} onClick={handleWishlist}>{wishlisted ? "♥" : "♡"}</button></div><Link to={`/product/${product.slug}`}><div className="product-info"><small>{product.brand_name || "TECH TOYS"}</small><h3>{product.name}</h3><div className="rating-row"><span>★ 4.8</span><span>{product.warranty_months}-month warranty</span></div><div className="price-row"><b>{money(product.price)}</b><del>{money(product.mrp)}</del>{discount > 0 && <strong>{discount}% off</strong>}</div><div className="spec-chips">{specs.map((spec) => <span key={spec}>{spec}</span>)}</div><span className={product.stock_qty > 0 ? "stock" : "stock out"}>{product.stock_qty > 0 ? `${product.stock_qty} in stock` : alertSet ? "Alert set — notify me" : "Notify me when back"}</span></div></Link></div>{feedback && <div className="cart-feedback" role="status">{feedback}</div>}<button disabled={product.stock_qty === 0 && alertSet} onClick={handleAction}>{product.stock_qty > 0 ? "Add to cart" : alertSet ? "Alert set ✓" : "Add alert"}</button></article>;
}

function DealCountdown({ endsAt }: { endsAt: string }) {
  const [remaining, setRemaining] = useState(0);
  useEffect(() => {
    function update() {
      const seconds = Math.max(0, Math.floor((new Date(endsAt).getTime() - Date.now()) / 1000));
      setRemaining(seconds);
    }
    update();
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [endsAt]);
  const hours = Math.floor(remaining / 3600);
  const minutes = Math.floor((remaining % 3600) / 60);
  const seconds = remaining % 60;
  const label = remaining > 0 ? `Ends in ${String(hours).padStart(2, "0")}h ${String(minutes).padStart(2, "0")}m ${String(seconds).padStart(2, "0")}s` : "Offer ended";
  return <time dateTime={endsAt}>{label}</time>;
}

function Home() {
  const products = useQuery({ queryKey: ["featured"], queryFn: () => api.products("featured=true&page_size=8") });
  const deals = useQuery({ queryKey: ["deals"], queryFn: api.deals });
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const heroProduct = products.data?.items[0];
  const heroPrice = heroProduct ? heroProduct.price : 999;
  const heroCategory = heroProduct ? productCategory(heroProduct) : "Earbuds";
  const offerText = settings.data?.offers || "1 year warranty; Secure checkout; Bill payment; 7 days replacement; Free shipping";
  const trustItems = offerText.split(";").map((item) => item.trim()).filter(Boolean).slice(0, 5);
  const categoryTiles = ["Headphones", "Watches", "Speakers", "Accessories"];
  return <Reveal><>
    <section className="hero"><div className="hero-copy"><p className="eyebrow">Curated for everyday listening</p><h1>True wireless<br/><em>earbuds.</em></h1><p className="hero-price">Starting from {money(heroPrice)}</p><p className="lede">Clean sound, honest advice and gadgets selected for the way you actually use them.</p><div className="hero-actions"><Link className="button dark-button" to="/shop">Shop products</Link><Link className="button light-button" to="/finder">Find by phone model</Link></div></div><div className="hero-art-card"><ProductIllustration category={heroCategory}/><span>Genuine-checked<br/>curated catalogue</span></div></section>
    <section className="trust-strip">{trustItems.map((item, index) => <span key={item}><b>{index === 0 ? "✓" : "•"}</b>{item}</span>)}</section>
    <section className="section category-section"><div className="section-heading"><div><p className="eyebrow">Browse the counter</p><h2>Shop by category</h2></div><Link to="/shop">View all →</Link></div><div className="category-grid">{categoryTiles.map((category) => <Link className="category-tile" key={category} to={`/shop?q=${encodeURIComponent(category)}`}><div className="category-mini-grid"><ProductIllustration category={category} compact/><ProductIllustration category={category} compact/><ProductIllustration category={category} compact/><ProductIllustration category={category} compact/></div><div><strong>{category}</strong><span>＋</span></div></Link>)}</div></section>
    <section className="section"><div className="section-heading"><div><p className="eyebrow">Picked for you</p><h2>Featured products</h2></div><Link to="/shop">See all products →</Link></div><div className="product-grid">{products.data?.items.map((product) => <ProductCard key={product.id} product={product}/>)}</div></section>
    <section className="deal-panel"><div><p className="eyebrow">Short window</p><h2>Flash deals for the next run</h2><p>Server-calculated prices, no surprises at checkout.</p></div><div className="deal-list">{deals.data?.slice(0, 2).map((deal) => <div className="deal" key={deal.product.id}><span>LIVE DEAL</span><strong>{deal.product.name}</strong><b>{money(deal.product.price)}</b><DealCountdown endsAt={deal.ends_at}/><Link to={`/product/${deal.product.slug}`}>View deal</Link></div>)}</div></section>
    <section className="home-cta section"><div><p className="eyebrow">Need a second opinion?</p><h2>Find the right fit for your phone.</h2><p>Choose your model and we will show compatible cables, covers and charging gear.</p></div><Link className="button dark-button" to="/finder">Open phone finder</Link></section>
  </></Reveal>;
}

function Shop() {
  const [params, setParams] = useSearchParams();
  const [filterOpen, setFilterOpen] = useState(false);
  const q = params.get("q") || "";
  const sort = params.get("sort") || "newest";
  const category = params.get("category") || "";
  const brand = params.get("brand") || "";
  const minPrice = params.get("min_price") || "";
  const maxPrice = params.get("max_price") || "";
  const inStock = params.get("in_stock") === "true";
  const warranty = params.get("warranty") === "true";
  const categories = useQuery({ queryKey: ["categories"], queryFn: api.categories });
  const brands = useQuery({ queryKey: ["brands"], queryFn: api.brands });
  const query = useQuery({
    queryKey: ["products", q, sort, category, brand, minPrice, maxPrice, inStock, warranty],
    queryFn: () => {
      const search = new URLSearchParams({ page_size: "60", sort });
      if (q) search.set("q", q);
      if (category) search.set("category", category);
      if (brand) search.set("brand", brand);
      if (minPrice) search.set("min_price", minPrice);
      if (maxPrice) search.set("max_price", maxPrice);
      if (inStock) search.set("in_stock", "true");
      if (warranty) search.set("warranty", "true");
      return api.products(search.toString());
    },
  });
  function updateFilter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next);
  }
  function clearFilters() {
    const next = new URLSearchParams();
    if (q) next.set("q", q);
    setParams(next);
    setFilterOpen(false);
  }
  const activeFilters = [
    category && `Category: ${category}`,
    brand && `Brand: ${brand}`,
    minPrice && `Min ₹${minPrice}`,
    maxPrice && `Max ₹${maxPrice}`,
    inStock && "In stock",
    warranty && "Warranty",
  ].filter(Boolean) as string[];
  return <section className="section page-section">
    <div className="page-intro"><p className="eyebrow">The counter catalogue</p><h1>Shop by what you need.</h1><p>Search by product, brand or SKU. Prices and stock are live from the shop backend.</p></div>
    <div className="shop-toolbar"><button className="button ghost mobile-filter-button" onClick={() => setFilterOpen(true)}>Filters{activeFilters.length > 0 ? ` (${activeFilters.length})` : ""}</button><span className="result-count">{query.data?.total ?? 0} products</span><select aria-label="Sort products by" value={sort} onChange={(event) => updateFilter("sort", event.target.value)}><option value="newest">Sort: Featured/newest</option><option value="price_asc">Price: low to high</option><option value="price_desc">Price: high to low</option><option value="name">Name: A to Z</option></select><Link className="button ghost" to="/finder">Find accessories</Link></div>
    <div className="shop-layout">
      <aside className={`shop-filters ${filterOpen ? "open" : ""}`}>
        <div className="filter-heading"><h2>Filter products</h2><button className="filter-close" aria-label="Close filters" onClick={() => setFilterOpen(false)}>×</button></div>
        <label>Search<input value={q} placeholder="Earbuds, charger…" onChange={(event) => updateFilter("q", event.target.value)}/></label>
        <label>Category<select value={category} onChange={(event) => updateFilter("category", event.target.value)}><option value="">All categories</option>{categories.data?.map((item) => <option key={item.id} value={item.slug}>{item.name}</option>)}</select></label>
        <label>Brand<select value={brand} onChange={(event) => updateFilter("brand", event.target.value)}><option value="">All brands</option>{brands.data?.map((item) => <option key={item.id} value={item.slug}>{item.name}</option>)}</select></label>
        <div className="price-filter"><label>Min price<input type="number" min="0" value={minPrice} placeholder="₹0" onChange={(event) => updateFilter("min_price", event.target.value)}/></label><label>Max price<input type="number" min="0" value={maxPrice} placeholder="₹10,000" onChange={(event) => updateFilter("max_price", event.target.value)}/></label></div>
        <label className="filter-check"><input type="checkbox" checked={inStock} onChange={(event) => updateFilter("in_stock", event.target.checked ? "true" : "")}/> In-stock only</label>
        <label className="filter-check"><input type="checkbox" checked={warranty} onChange={(event) => updateFilter("warranty", event.target.checked ? "true" : "")}/> Warranty included</label>
        <button className="button ghost full" onClick={clearFilters}>Clear filters</button>
      </aside>
      {filterOpen && <button className="filter-backdrop" aria-label="Close filters" onClick={() => setFilterOpen(false)}/>} 
      <div className="shop-results">
        {activeFilters.length > 0 && <div className="active-filters" aria-label="Active filters">{activeFilters.map((filter) => <button key={filter} onClick={clearFilters}>{filter} ×</button>)}</div>}
        {query.isLoading && <div className="skeleton-grid"><span/><span/><span/><span/></div>}
        {query.isError && <div className="notice error">Could not load products. Please try again in a moment.</div>}
        {!query.isLoading && !query.isError && query.data?.total === 0 && <div className="empty"><h3>No exact match yet.</h3><p>Try a broader word or ask the assistant for a recommendation.</p></div>}
        <div className="product-grid">{query.data?.items.map((product) => <ProductCard key={product.id} product={product}/>)}</div>
      </div>
    </div>
  </section>;
}

function ProductPage() {
  const params = useParams(); const product = useQuery({ queryKey: ["product", params.slug], queryFn: () => api.product(params.slug || "") }); const add = useStore((state) => state.add); const requestAlert = useStore((state) => state.requestAlert); const alertSet = useStore((state) => state.alertIds.includes(product.data?.id || -1)); const [feedback, setFeedback] = useState("");
  if (product.isLoading) return <section className="section page-section"><div className="skeleton-large"/></section>;
  if (product.isError || !product.data) return <section className="section page-section"><div className="notice error">Product not found.</div></section>;
  const item = product.data;
  function addToCart() { if (item.stock_qty > 0) { add(item); setFeedback("Added to cart +1"); } else { requestAlert(item.id); setFeedback("Stock alert set ✓"); } window.setTimeout(() => setFeedback(""), 2200); }
  return <section className="section page-section product-detail"><div className="detail-gallery"><div className="detail-art"><ProductIllustration category={productCategory(item)}/><span>{productCategory(item)}</span><i>PRODUCT ILLUSTRATION</i></div><div className="gallery-thumbs"><ProductIllustration category={productCategory(item)} compact/><ProductIllustration category={productCategory(item)} compact/></div></div><div className="detail-copy"><p className="eyebrow">{item.brand_name} / {item.sku}</p><h1>{item.name}</h1><p>{item.description}</p><div className="detail-price"><b>{money(item.price)}</b><del>{money(item.mrp)}</del></div><div className="badges"><span>✓ {item.warranty_months}-month warranty</span><span>✓ Genuine-verified stock</span></div>{feedback && <div className="cart-feedback" role="status">{feedback}</div>}<button className="button primary" disabled={item.stock_qty === 0 && alertSet} onClick={addToCart}>{item.stock_qty > 0 ? "Add to cart" : alertSet ? "Alert set ✓" : "Add alert"}</button><div className="spec-list"><strong>What you should know</strong><p>{item.stock_qty > 0 ? `Only ${item.stock_qty} units currently visible in shop stock.` : "Out of stock — use Notify me and we will alert you."}</p><p>Server-side price and stock validation happens at checkout.</p></div></div></section>;
}

function Finder() {
  const [term, setTerm] = useState(""); const [selected, setSelected] = useState(""); const phones = useQuery({ queryKey: ["phones", term], queryFn: () => api.phones(term), enabled: term.length > 1 }); const result = useQuery({ queryKey: ["compatible", selected], queryFn: () => api.compatible(selected), enabled: selected.length > 0 });
  return <section className="section page-section"><div className="page-intro narrow"><p className="eyebrow">Find by phone model</p><h1>Make the right accessory fit.</h1><p>Choose a phone model and we will group compatible protection and charging products.</p></div><div className="finder-box"><label htmlFor="phone">Your phone model</label><input id="phone" value={term} onChange={(event) => { setTerm(event.target.value); setSelected(""); }} placeholder="Try Redmi Note 13"/>{phones.data && <div className="suggestions">{phones.data.map((phone) => <button key={phone.id} onClick={() => { setTerm(`${phone.brand} ${phone.model_name}`); setSelected(phone.slug); }}>{phone.brand} {phone.model_name}<small>{phone.connector_type}</small></button>)}</div>}</div>{result.data && <div className="compatibility"><h2>Made for {result.data.phone.model_name}</h2>{Object.entries(result.data.groups).map(([group, items]) => items.length > 0 && <div key={group}><h3>{group}</h3><div className="product-grid compact">{items.slice(0, 4).map((item) => <ProductCard key={item.id} product={item}/>)}</div></div>)}</div>}</section>;
}

function Wishlist() {
  const wishlist = useStore((state) => state.wishlist);
  return <section className="section page-section wishlist-page"><div className="page-intro"><p className="eyebrow">Saved products</p><h1>Your shortlist.</h1><p>Keep products here while you compare prices, stock and compatibility.</p></div>{wishlist.length === 0 ? <div className="empty"><h3>Your wishlist is empty.</h3><p>Tap the heart on any product to save it here.</p><Link className="button light-button" to="/shop">Browse products</Link></div> : <div className="product-grid">{wishlist.map((product) => <ProductCard key={product.id} product={product}/>)}</div>}</section>;
}

function Cart() {
  const cart = useStore((state) => state.cart); const remove = useStore((state) => state.remove); const setQty = useStore((state) => state.setQty); const total = cart.reduce((sum, item) => sum + item.product.price * item.qty, 0);
  return <section className="section page-section"><div className="page-intro"><p className="eyebrow">Your basket</p><h1>Ready when you are.</h1></div>{cart.length === 0 ? <div className="empty"><h3>Your cart is empty.</h3><Link className="button primary" to="/shop">Browse products</Link></div> : <div className="cart-layout"><div className="cart-lines">{cart.map((item) => <div className="cart-line" key={item.product.id}><div className="mini-art">{item.product.name.slice(0,1)}</div><div><strong>{item.product.name}</strong><small>{money(item.product.price)} each</small></div><input aria-label="Quantity" type="number" min="1" value={item.qty} onChange={(event) => setQty(item.product.id, Number(event.target.value))}/><b>{money(item.product.price * item.qty)}</b><button onClick={() => remove(item.product.id)}>Remove</button></div>)}</div><aside className="summary"><h3>Order summary</h3><p><span>Items</span><b>{money(total)}</b></p><p><span>Delivery</span><b>Calculated next</b></p><hr/><p className="total"><span>Subtotal</span><b>{money(total)}</b></p><Link className="button primary full" to="/checkout">Continue to checkout</Link></aside></div>}</section>;
}

function Checkout() {
  const cart = useStore((state) => state.cart); const clear = useStore((state) => state.clear); const [phone, setPhone] = useState(""); const [message, setMessage] = useState(""); const [order, setOrder] = useState<Order | null>(null); const [loading, setLoading] = useState(false);
  async function submit() { setLoading(true); try { if (!localStorage.getItem("tech-toys-token")) { const otp = await api.otp({ phone }); if (!otp.demo_otp) throw new Error("OTP delivery is not configured for this demo."); const session = await api.verifyOtp({ phone, code: otp.demo_otp, name: "Shop customer" }); localStorage.setItem("tech-toys-token", session.access_token); } const result = await api.order({ items: cart.map((item) => ({ product_id: item.product.id, qty: item.qty })), payment_method: "pay_at_shop", fulfilment: "pickup_15min", address: "Sagar Market pickup", note: `Customer phone: ${phone}` }); setOrder(result); clear(); } catch (error) { setMessage(error instanceof Error ? error.message : "Could not place order."); } finally { setLoading(false); } }
  if (order) return <section className="section page-section"><div className="success-card"><span className="success-icon">✓</span><p className="eyebrow">Order received</p><h1>{order.order_no}</h1><p>Your {money(order.total)} pickup order is now in the shop queue.</p><Link className="button primary" to={`/track?order=${order.order_no}&phone=${phone}`}>Track this order</Link></div></section>;
  return <section className="section page-section narrow-page"><div className="page-intro"><p className="eyebrow">Secure checkout</p><h1>One last detail.</h1><p>We use your phone only to share order updates.</p></div><div className="checkout-form"><label>Phone number<input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="9876500001"/></label><label>Fulfilment<select defaultValue="pickup"><option value="pickup">15-minute pickup at Sagar Market</option><option value="delivery">Same-day Kanpur delivery</option></select></label><div className="payment-choice"><b>Pay at shop</b><span>UPI QR and COD options are supported by the backend.</span></div>{message && <div className="notice error">{message}</div>}<button className="button primary full" disabled={loading || phone.length < 7 || cart.length === 0} onClick={submit}>{loading ? "Placing order…" : "Place pickup order"}</button></div></section>;
}

function Track() {
  const [params] = useSearchParams(); const [orderNo, setOrderNo] = useState(params.get("order") || ""); const [phone, setPhone] = useState(params.get("phone") || ""); const [order, setOrder] = useState<Order | null>(null); const [error, setError] = useState("");
  async function find() { try { setError(""); setOrder(await api.track(orderNo, phone)); } catch (value) { setError(value instanceof Error ? value.message : "No order found."); } }
  return <section className="section page-section narrow-page"><div className="page-intro"><p className="eyebrow">Order tracking</p><h1>Know where it is.</h1></div><div className="checkout-form"><label>Order number<input value={orderNo} onChange={(event) => setOrderNo(event.target.value)} placeholder="TT-AB12CD34"/></label><label>Phone number<input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="9876500001"/></label><button className="button primary full" onClick={find}>Show status</button>{error && <div className="notice error">{error}</div>}</div>{order && <div className="timeline"><div className="order-head"><strong>{order.order_no}</strong><span>{order.status.replace(/_/g, " ")}</span><b>{money(order.total)}</b></div>{order.events.map((event) => <div className="timeline-row" key={`${event.status}-${event.created_at}`}><i/><div><strong>{event.status.replace(/_/g, " ")}</strong><p>{event.note}</p></div></div>)}</div>}</section>;
}

function Repair() { const [sent, setSent] = useState(false); return <section className="section page-section narrow-page"><div className="page-intro"><p className="eyebrow">Walk-in repairs</p><h1>Bring the stubborn thing in.</h1><p>Tell us what is wrong. We will keep the ticket moving and call before paid work.</p></div>{sent ? <div className="success-card"><span className="success-icon">✓</span><h2>Repair request received</h2><p>Sign in with phone OTP to see the ticket timeline.</p></div> : <form className="checkout-form" onSubmit={(event) => { event.preventDefault(); setSent(true); }}><label>Device brand<input required placeholder="Samsung, Redmi…"/></label><label>Model<input required placeholder="Model name"/></label><label>What is wrong?<textarea required placeholder="Charging port, cracked screen…"/></label><label>Preferred slot<input placeholder="Tomorrow, 5–7 PM"/></label><button className="button primary full">Book repair slot</button></form>}</section>; }

function Admin() { const navigate = useNavigate(); const dashboard = useQuery({ queryKey: ["admin-dashboard"], queryFn: api.adminDashboard }); const orders = useQuery({ queryKey: ["admin-orders"], queryFn: api.adminOrders }); const [login, setLogin] = useState({ email: "admin@demo.shop", password: "Admin@123" }); const [loggedIn, setLoggedIn] = useState(Boolean(localStorage.getItem("tech-toys-token"))); async function signIn() { try { const result = await api.login(login); localStorage.setItem("tech-toys-token", result.access_token); setLoggedIn(true); } catch { alert("Use the demo admin credentials from README."); } } if (!loggedIn) return <section className="section page-section narrow-page"><div className="admin-login"><p className="eyebrow">Owner console</p><h1>Counter control room.</h1><input value={login.email} onChange={(event) => setLogin({ ...login, email: event.target.value })}/><input type="password" value={login.password} onChange={(event) => setLogin({ ...login, password: event.target.value })}/><button className="button primary full" onClick={signIn}>Sign in as admin</button></div></section>; return <section className="section page-section"><div className="admin-head"><div><p className="eyebrow">Owner console</p><h1>Good morning, keep it moving.</h1></div><button className="button ghost" onClick={() => { localStorage.removeItem("tech-toys-token"); navigate("/"); }}>Sign out</button></div><div className="metrics"><div><small>All sales</small><strong>{money(dashboard.data?.sales || 0)}</strong></div><div><small>Today</small><strong>{money(dashboard.data?.today_sales || 0)}</strong></div><div><small>Orders</small><strong>{dashboard.data?.orders || 0}</strong></div><div><small>Low stock</small><strong>{dashboard.data?.low_stock.length || 0}</strong></div></div><div className="admin-grid"><div className="admin-panel"><div className="section-heading"><h2>Latest orders</h2><span>Live queue</span></div>{orders.data?.slice(0, 8).map((order) => <div className="admin-order" key={order.order_no}><div><strong>{order.order_no}</strong><small>{order.payment_status} · {money(order.total)}</small></div><select value={order.status} onChange={(event) => api.adminStatus(order.order_no, event.target.value).then(() => window.location.reload())}><option>new</option><option>confirmed</option><option>packed</option><option>ready_for_pickup</option><option>out_for_delivery</option><option>delivered</option><option>cancelled</option></select></div>)}</div><div className="admin-panel"><div className="section-heading"><h2>Low-stock watch</h2></div>{dashboard.data?.low_stock.map((item) => <div className="stock-row" key={item.name}><span>{item.name}</span><b>{item.stock_qty}</b></div>)}</div></div></section>; }

function Assistant() { const [open, setOpen] = useState(false); const [text, setText] = useState(""); const [reply, setReply] = useState<{ reply: string; products: Product[] } | null>(null); async function ask() { if (text.trim() === "") return; setReply(await api.assistant(text)); setText(""); } return <div className="assistant"><button className="assistant-toggle" onClick={() => setOpen(!open)}>Ask TT</button>{open && <div className="assistant-panel"><strong>Tell me what you need</strong><p>Try “2000 tak ke earbuds” or “charger for my phone”.</p>{reply && <div className="assistant-reply"><p>{reply.reply}</p>{reply.products.map((product) => <Link key={product.id} to={`/product/${product.slug}`}>{product.name} · {money(product.price)}</Link>)}</div>}<div className="assistant-input"><input value={text} onChange={(event) => setText(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void ask(); }} placeholder="Ask the counter…"/><button onClick={() => void ask()}>→</button></div></div>}</div>; }

function App() { return <Layout><Routes><Route path="/" element={<Home/>}/><Route path="/shop" element={<Shop/>}/><Route path="/product/:slug" element={<ProductPage/>}/><Route path="/finder" element={<Finder/>}/><Route path="/wishlist" element={<Wishlist/>}/><Route path="/cart" element={<Cart/>}/><Route path="/checkout" element={<Checkout/>}/><Route path="/track" element={<Track/>}/><Route path="/repair" element={<Repair/>}/><Route path="/admin" element={<AdminPortal/>}/><Route path="*" element={<Home/>}/></Routes><Assistant/></Layout>; }

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter><App/></BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
