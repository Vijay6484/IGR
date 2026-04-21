import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link, useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';
import html2pdf from 'html2pdf.js';

// const API_BASE_URL = 'https://api.mahasuchi.com/api';
const API_BASE_URL = 'http://localhost:8000/api';

// --- Shared Components ---
const TopAppBar = () => {
    return (
        <header className="fixed w-full top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-slate-200/60 shadow-sm dark:bg-slate-900/95 dark:border-slate-800 transition-all">
            <nav className="flex justify-between items-center px-5 py-4 max-w-7xl mx-auto w-full">
                <Link to="/" className="hover:opacity-90 transition-opacity">
                    <img src="/logo.jpeg" alt="Mahasuchi" className="h-10 md:h-12 w-auto object-contain" />
                </Link>
                <div className="flex items-center gap-4">
                    <div className="hidden lg:flex items-center gap-6 text-sm font-bold text-slate-600">
                        <Link to="/" className="hover:text-azure transition-colors">Home</Link>
                        <Link to="/about" className="hover:text-azure transition-colors">About Us</Link>
                        <Link to="/contact" className="hover:text-azure transition-colors">Contact</Link>
                    </div>
                    <button className="lg:hidden flex items-center justify-center border border-slate-200 bg-white dark:bg-slate-800 dark:border-slate-700 rounded-full w-12 h-12 hover:bg-slate-50 hover:shadow-md hover:scale-105 active:scale-95 transition-all shadow-sm">
                        <span className="material-symbols-outlined text-slate-700 dark:text-slate-300 text-2xl">menu</span>
                    </button>
                </div>
            </nav>
        </header>
    );
};

const BottomNavBar = () => {
    const location = useLocation();
    const isActive = (path) => location.pathname === path || (path === '/search' && location.pathname !== '/');

    return (
        <nav className="lg:hidden fixed bottom-0 left-0 w-full z-50 flex justify-around items-center h-20 px-4 pb-safe bg-white/95 backdrop-blur-md border-t border-slate-100 shadow-[0_-4px_25px_rgba(0,0,0,0.06)] transition-all">
            <Link to="/" className={`flex flex-col items-center justify-center transition-all flex-1 ${isActive('/') ? 'text-azure scale-110' : 'text-slate-400 hover:text-slate-600'}`}>
                <span className="material-symbols-outlined text-[26px]">home</span>
                <span className="text-[10px] font-extrabold uppercase tracking-widest mt-1.5">Home</span>
            </Link>
            <Link to="/" className={`flex flex-col items-center justify-center transition-all flex-1 ${isActive('/search') ? 'text-azure scale-110' : 'text-slate-400 hover:text-slate-600'}`}>
                <span className="material-symbols-outlined text-[26px]">pageview</span>
                <span className="text-[10px] font-extrabold uppercase tracking-widest mt-1.5">Search</span>
            </Link>
            <div className="flex flex-col items-center justify-center text-slate-400 flex-1 hover:text-slate-600 cursor-pointer transition-colors">
                <span className="material-symbols-outlined text-[26px]">verified_user</span>
                <span className="text-[10px] font-extrabold uppercase tracking-widest mt-1.5">Verify</span>
            </div>
        </nav>
    );
};

const HomePage = () => {
    const navigate = useNavigate();
    const [locationsData, setLocationsData] = useState({});

    // Auto-select defaults
    const [selectedDistrict, setSelectedDistrict] = useState('पुणे');
    const [selectedTaluka, setSelectedTaluka] = useState('');
    const [selectedVillage, setSelectedVillage] = useState('');
    const [query, setQuery] = useState('');
    const [propertyType, setPropertyType] = useState('land');

    useEffect(() => {
        fetch(`${API_BASE_URL}/locations`)
            .then(res => res.json())
            .then(data => {
                setLocationsData(data);
                if (data['पुणे']) {
                    setSelectedDistrict('पुणे');
                }
            })
            .catch(err => console.error("Error fetching locations:", err));
    }, []);

    const districts = Object.keys(locationsData);
    const talukas = selectedDistrict && locationsData[selectedDistrict] ? Object.keys(locationsData[selectedDistrict]) : [];
    const villages = selectedTaluka && locationsData[selectedDistrict][selectedTaluka] ? locationsData[selectedDistrict][selectedTaluka] : [];

    const handleSearch = (e) => {
        e.preventDefault();
        if (!selectedDistrict || !selectedTaluka || !selectedVillage || !query) {
            alert("Please fill all fields.");
            return;
        }
        const params = new URLSearchParams({
            district: selectedDistrict,
            taluka: selectedTaluka,
            village: selectedVillage,
            query: query,
            propertyType: propertyType
        });
        navigate(`/results?${params.toString()}`);
    };

    const handleQueryChange = (e) => {
        const val = e.target.value;
        if (val === '' || /^[0-9\b]+$/.test(val)) {
            setQuery(val);
        }
    };

    return (
        <div className="min-h-screen flex flex-col bg-slate-50 overflow-x-hidden">
            <TopAppBar />
            <main className="flex-1 pt-28 lg:pt-[130px] pb-16 px-4 md:px-8">
                <div className="max-w-7xl mx-auto w-full grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-16 items-center">

                    {/* Left Column - Desktop Content */}
                    <div className="hidden lg:flex lg:col-span-6 xl:col-span-7 flex-col space-y-8 pr-4">
                        <div className="inline-flex items-center gap-2.5 px-4 py-2 bg-blue-100/50 text-blue-800 rounded-full font-bold text-xs uppercase tracking-widest border border-blue-200/50 w-fit backdrop-blur-sm">
                            <span className="material-symbols-outlined text-sm">public</span>
                            Official Gov. Database Indexed
                        </div>
                        <h1 className="text-5xl xl:text-6xl font-black text-primary leading-[1.1] tracking-tight">
                            Access Your <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-cyan-500">Land Records</span> Instantly.
                        </h1>
                        <p className="text-slate-500 text-lg xl:text-xl font-medium leading-relaxed max-w-xl">
                            Search your digital property documents through India's fastest and most reliable portal.
                            Skip the queues and access Index II databases natively.
                        </p>

                        <div className="grid grid-cols-2 gap-6 pt-4">
                            <div className="bg-white p-6 rounded-3xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow group cursor-pointer">
                                <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-2xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                                    <span className="material-symbols-outlined text-2xl">picture_as_pdf</span>
                                </div>
                                <h3 className="font-bold text-slate-800 text-lg mb-1">Original PDFs</h3>
                                <p className="text-sm text-slate-500 font-medium">Download historically scanned and verified official registry documents.</p>
                            </div>
                            <div className="bg-white p-6 rounded-3xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow group cursor-pointer">
                                <div className="w-12 h-12 bg-cyan-50 text-cyan-600 rounded-2xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                                    <span className="material-symbols-outlined text-2xl">database</span>
                                </div>
                                <h3 className="font-bold text-slate-800 text-lg mb-1">Deep Indexing</h3>
                                <p className="text-sm text-slate-500 font-medium">Over 2 million active records successfully digitized and locally available.</p>
                            </div>
                        </div>

                        <div className="pt-2 flex items-center gap-4 text-slate-400 font-semibold text-sm">
                            <div className="flex -space-x-4">
                                <img className="w-10 h-10 border-2 border-white rounded-full bg-slate-200" src="https://i.pravatar.cc/100?img=1" alt="User" />
                                <img className="w-10 h-10 border-2 border-white rounded-full bg-slate-200" src="https://i.pravatar.cc/100?img=2" alt="User" />
                                <img className="w-10 h-10 border-2 border-white rounded-full bg-slate-200" src="https://i.pravatar.cc/100?img=3" alt="User" />
                                <div className="w-10 h-10 border-2 border-white rounded-full bg-slate-100 flex items-center justify-center text-xs font-bold text-slate-600">2M+</div>
                            </div>
                            Trusted by thousands daily
                        </div>
                    </div>

                    {/* Right Column - Search Form */}
                    <div className="lg:col-span-6 xl:col-span-5 w-full flex justify-center lg:justify-end perspective-1000">
                        <div className="w-full max-w-[440px] bg-white border border-slate-200/80 rounded-[2rem] p-7 md:p-8 shadow-2xl shadow-blue-900/10 lg:hover:-translate-y-1 transition-transform duration-500 relative overflow-hidden">

                            {/* Decorative Blur Backgrounds */}
                            <div className="absolute top-0 right-0 w-32 h-32 bg-blue-100/50 rounded-full blur-3xl -mr-10 -mt-10 pointer-events-none"></div>

                            <div className="flex flex-col items-center gap-3 mb-8 relative z-10">
                                <div className="bg-primary text-white p-3.5 rounded-2xl mb-1 shadow-lg shadow-primary/20">
                                    <span className="material-symbols-outlined text-2xl font-bold">search_check</span>
                                </div>
                                <h2 className="text-2xl font-extrabold text-slate-800 tracking-tight text-center">E-Search Form 2.0</h2>
                                <p className="text-slate-500 text-xs font-semibold px-2 text-center uppercase tracking-wider">Locate verified Property Details</p>
                            </div>

                            <form className="space-y-5 relative z-10" onSubmit={handleSearch}>
                                <div className="space-y-1.5 group">
                                    <label className="block text-[11px] font-bold uppercase tracking-[0.1em] text-slate-500 px-1 transition-colors group-hover:text-primary">District</label>
                                    <div className="relative transition-all border border-slate-200 rounded-xl bg-slate-50 hover:border-blue-300 focus-within:border-blue-500 focus-within:ring-4 focus-within:ring-blue-500/10">
                                        <select
                                            className="w-full bg-transparent border-0 focus:ring-0 text-slate-800 font-bold text-sm py-4 px-5 appearance-none outline-none cursor-pointer"
                                            value={selectedDistrict}
                                            onChange={(e) => { setSelectedDistrict(e.target.value); setSelectedTaluka(''); setSelectedVillage(''); }}
                                            required
                                        >
                                            <option value="">Select District</option>
                                            {districts.map(d => <option key={d} value={d}>{d}</option>)}
                                        </select>
                                    </div>
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-1.5 group">
                                        <label className="block text-[11px] font-bold uppercase tracking-[0.1em] text-slate-500 px-1 transition-colors group-hover:text-primary">Taluka</label>
                                        <div className="relative transition-all border border-slate-200 rounded-xl bg-slate-50 hover:border-blue-300 focus-within:border-blue-500 focus-within:ring-4 focus-within:ring-blue-500/10">
                                            <select
                                                className="w-full bg-transparent border-0 focus:ring-0 text-slate-800 font-bold text-sm py-4 px-4 appearance-none outline-none cursor-pointer"
                                                value={selectedTaluka}
                                                onChange={(e) => { setSelectedTaluka(e.target.value); setSelectedVillage(''); }}
                                                disabled={!selectedDistrict}
                                                required
                                            >
                                                <option value="">Select</option>
                                                {talukas.map(t => <option key={t} value={t}>{t}</option>)}
                                            </select>
                                        </div>
                                    </div>
                                    <div className="space-y-1.5 group">
                                        <label className="block text-[11px] font-bold uppercase tracking-[0.1em] text-slate-500 px-1 transition-colors group-hover:text-primary">Village</label>
                                        <div className="relative transition-all border border-slate-200 rounded-xl bg-slate-50 hover:border-blue-300 focus-within:border-blue-500 focus-within:ring-4 focus-within:ring-blue-500/10">
                                            <select
                                                className="w-full bg-transparent border-0 focus:ring-0 text-slate-800 font-bold text-sm py-4 px-4 appearance-none outline-none cursor-pointer"
                                                value={selectedVillage}
                                                onChange={(e) => setSelectedVillage(e.target.value)}
                                                disabled={!selectedTaluka}
                                                required
                                            >
                                                <option value="">Select</option>
                                                {villages.map(v => <option key={v} value={v}>{v}</option>)}
                                            </select>
                                        </div>
                                    </div>
                                </div>

                                <div className="space-y-1.5 group">
                                    <label className="block text-[11px] font-bold uppercase tracking-[0.1em] text-slate-500 px-1 transition-colors group-hover:text-primary">Property Type &amp; Number</label>
                                    <div className="flex gap-2">
                                        {/* Property Type Dropdown */}
                                        <div className="relative border border-slate-200 rounded-xl bg-slate-50 hover:border-blue-300 focus-within:border-blue-500 focus-within:ring-4 focus-within:ring-blue-500/10 flex-shrink-0">
                                            <select
                                                className="bg-transparent border-0 focus:ring-0 text-slate-700 font-bold text-[11px] py-4 pl-3 pr-6 appearance-none outline-none cursor-pointer h-full"
                                                value={propertyType}
                                                onChange={(e) => setPropertyType(e.target.value)}
                                            >
                                                <option value="land">Plot/Gut/Survey/CTS</option>
                                                <option value="flat">Flat/Shop/Office</option>
                                            </select>
                                        </div>
                                        {/* Property Number Input */}
                                        <div className="relative flex-1 transition-all border border-slate-200 rounded-xl bg-slate-50 hover:border-blue-300 focus-within:border-blue-500 focus-within:ring-4 focus-within:ring-blue-500/10 overflow-hidden">
                                            <input
                                                className="w-full bg-transparent border-0 focus:ring-0 text-slate-800 font-bold text-sm py-4 pl-10 pr-8 outline-none"
                                                placeholder="Ex: 128"
                                                required
                                                type="text"
                                                value={query}
                                                onChange={handleQueryChange}
                                            />
                                            <div className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                                                <span className="material-symbols-outlined text-[18px]">pin</span>
                                            </div>
                                            {query && (
                                                <div className="absolute inset-y-0 right-0 flex items-center pr-3 text-green-500">
                                                    <span className="material-symbols-outlined text-[18px] font-bold">check_circle</span>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                                <div className="space-y-3 pt-3">
                                    <div className="flex items-start gap-3 px-1">
                                        <input id="accept-terms" type="checkbox" required className="mt-0.5 w-5 h-5 rounded-md border-slate-300 text-azure focus:ring-azure cursor-pointer" />
                                        <label htmlFor="accept-terms" className="text-xs text-slate-500 font-medium leading-tight cursor-pointer">
                                            I agree to the terms of public search mapping criteria and declare searches are for lawful checks.
                                        </label>
                                    </div>
                                </div>
                                <div className="pt-5">
                                    <button className="w-full bg-primary hover:bg-slate-800 text-white font-black py-4 rounded-xl shadow-xl shadow-primary/25 transition-all hover:scale-[1.02] active:scale-[0.98] text-sm uppercase tracking-widest flex items-center justify-center gap-3" type="submit">
                                        <span className="material-symbols-outlined text-[20px]">database_search</span>
                                        Verify Records
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </main>
            <footer className="bg-primary text-white py-12 lg:py-16 px-6 relative z-10 w-full mt-auto mb-20 lg:mb-0">
                <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-8 md:gap-0">
                    <div className="text-center md:text-left">
                        <div className="flex items-center justify-center md:justify-start gap-3 mb-4">
                            <div className="w-10 h-10 bg-azure/20 rounded-xl flex items-center justify-center">
                                <span className="material-symbols-outlined text-azure">shield</span>
                            </div>
                            <span className="font-black text-2xl tracking-tight">Mahasuchi</span>
                        </div>
                        <p className="text-slate-400 text-xs md:text-sm font-medium max-w-sm leading-relaxed">
                            Providing a sovereign, fast, and digitized public foundation for property administration in Maharashtra.
                        </p>
                    </div>

                    <div className="flex gap-6 lg:gap-10 text-[10px] md:text-xs font-bold uppercase tracking-widest text-slate-300">
                        <Link to="/privacy" className="hover:text-white transition-colors">Privacy</Link>
                        <Link to="/terms" className="hover:text-white transition-colors">Terms</Link>
                        <Link to="#" className="hover:text-white transition-colors">API Portal</Link>
                        <Link to="/contact" className="hover:text-white transition-colors">Contact</Link>
                    </div>
                </div>

                <div className="max-w-7xl mx-auto pt-8 mt-8 border-t border-white/10 text-center md:text-left flex flex-col md:flex-row justify-between items-center gap-4 pb-10 lg:pb-0">
                    <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold">
                        © 2026 We make your property experience <span className="text-azure ml-1">SUPER FAST</span>
                    </p>
                    <div className="flex gap-3">
                        <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center hover:bg-slate-700 cursor-pointer">
                            <span className="material-symbols-outlined text-sm">share</span>
                        </div>
                    </div>
                </div>
            </footer>

        </div>
    );
};

// Loading and Results code remaining essentially identical but polished slightly 
// Loading Page is now handled inside ResultsPage for smoother UX,
// but we keep the component if anyone navigates to it directly.
const LoadingPage = () => {
    const navigate = useNavigate();
    const location = useLocation();
    useEffect(() => {
        navigate(`/results${location.search}`, { replace: true });
    }, [navigate, location]);
    return null;
};

// ─── Lead Capture Modal ──────────────────────────────────────────────────────
const LeadCaptureModal = ({ isOpen, onClose, onSubmit }) => {
    const [email, setEmail] = useState('');
    const [phone, setPhone] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    if (!isOpen) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!email || !phone) return alert('Please enter both email and phone.');
        setIsSubmitting(true);
        await onSubmit({ email, phone });
        setIsSubmitting(false);
    };

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={onClose}></div>
            <div className="bg-white rounded-[2rem] shadow-2xl relative z-10 w-full max-w-md p-8 md:p-10 overflow-hidden transform animate-in fade-in zoom-in duration-300">
                <div className="absolute top-0 left-0 w-full h-2 bg-gradient-to-r from-blue-600 to-cyan-500"></div>
                
                <div className="flex flex-col items-center text-center space-y-4">
                    <div className="w-16 h-16 bg-blue-50 text-blue-600 rounded-2xl flex items-center justify-center mb-2">
                        <span className="material-symbols-outlined text-3xl">contact_mail</span>
                    </div>
                    <h3 className="text-2xl font-black text-slate-800">Final Step</h3>
                    <p className="text-slate-500 text-sm font-medium leading-relaxed">
                        Please provide your contact details to receive your verified search report. 
                        <span className="block mt-2 text-[11px] text-slate-400 italic">This data is collected for product development purposes to improve our services.</span>
                    </p>
                </div>

                <form onSubmit={handleSubmit} className="mt-8 space-y-4">
                    <div className="space-y-1.5">
                        <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest ml-1">Email Address</label>
                        <input
                            required type="email" value={email} onChange={e => setEmail(e.target.value)}
                            placeholder="example@gmail.com"
                            className="w-full px-5 py-4 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all text-slate-800 font-semibold"
                        />
                    </div>
                    <div className="space-y-1.5">
                        <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest ml-1">Phone Number</label>
                        <input
                            required type="tel" value={phone} onChange={e => setPhone(e.target.value)}
                            placeholder="Mobile Number"
                            className="w-full px-5 py-4 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all text-slate-800 font-semibold"
                        />
                    </div>
                    
                    <button
                        type="submit" disabled={isSubmitting}
                        className="w-full mt-6 bg-primary hover:bg-slate-800 text-white font-black py-4 rounded-xl shadow-xl shadow-primary/25 transition-all hover:scale-[1.02] active:scale-[0.98] text-sm uppercase tracking-widest flex items-center justify-center gap-3"
                    >
                        {isSubmitting ? 'Processing...' : 'Continue to Payment'}
                        <span className="material-symbols-outlined text-[20px]">arrow_forward</span>
                    </button>

                    <button type="button" onClick={onClose} className="w-full text-slate-400 font-bold text-xs hover:text-slate-600 transition-colors py-2">
                        Cancel
                    </button>
                </form>
            </div>
        </div>
    );
};


const ResultsPage = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [records, setRecords] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const district = searchParams.get('district');
    const taluka = searchParams.get('taluka');
    const village = searchParams.get('village');
    const query = searchParams.get('query');
    const propertyType = searchParams.get('propertyType') || 'land';
    // Exact type strings from the database property_numbers[].type field
    const LAND_TYPES = new Set([
        'gut_number', 'survey_number', 'milkat_number',
        'plot_number', 'cts_number', 'bhumapan_number', 'block_number'
    ]);
    const FLAT_TYPES = new Set([
        'flat_number', 'shop_number', 'sadanika_number'
    ]);

    const matchesType = (record) => {
        const nums = record.property_numbers || [];
        if (nums.length === 0) return true; // unclassified — show in both
        if (propertyType === 'land') {
            return nums.some(n => LAND_TYPES.has(n.type));
        } else {
            return nums.some(n => FLAT_TYPES.has(n.type));
        }
    };

    // Format date: show only dd/mm + blurred dummy year
    const formatDate = (dateStr) => {
        if (!dateStr) return null;
        const match = dateStr.match(/(\d{1,2})[\/\-](\d{1,2})/);
        if (match) return { ddmm: `${match[1].padStart(2, '0')}/${match[2].padStart(2, '0')}` };
        return { ddmm: dateStr };
    };

    useEffect(() => {
        setLoading(true);
        fetch(`${API_BASE_URL}/search?district=${encodeURIComponent(district)}&taluka=${encodeURIComponent(taluka)}&village=${encodeURIComponent(village)}&query=${encodeURIComponent(query)}`)
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    setError(data.error);
                } else {
                    const raw = data.results || [];
                    const seen = new Map();
                    const unique = [];
                    for (const rec of raw) {
                        const key = rec.pdf_link ? rec.pdf_link : `${rec.document_number}|${rec.date}|${rec.document_type}`;
                        if (!seen.has(key)) { seen.set(key, true); unique.push(rec); }
                    }
                    setRecords(unique);
                }
                setTimeout(() => setLoading(false), 800); // Small buffer for visual smoothness
            })
            .catch(err => {
                console.error(err);
                setError("Failed to fetch records");
                setLoading(false);
            });
    }, [district, taluka, village, query]);

    const filteredRecords = records.filter(matchesType);

    const [isPaying, setIsPaying] = useState(false);
    const [paymentError, setPaymentError] = useState(null);
    const [showLeadModal, setShowLeadModal] = useState(false);


    // ── PDF Build Helper ────────────────────
    const buildAndDownloadPdf = async (records, ctx) => {
        const { district: d, taluka: t, village: v, query: q } = ctx;
        const logoRes = await fetch('/logo.jpeg');
        const logoBlob = await logoRes.blob();
        const logoBase64 = await new Promise((resolve) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.readAsDataURL(logoBlob);
        });

        const FIELDS = [
            { key: 'document_type', label: 'Document Type' },
            { key: 'registration_office', label: 'Registration Office' },
            { key: 'date', label: 'Date of Registration' },
            { key: 'seller_party', label: 'Seller / Executor Party' },
            { key: 'buyer_party', label: 'Buyer / Claimant Party' },
            { key: 'text', label: 'Property Description' },
            { key: 'district', label: 'District' },
            { key: 'taluka', label: 'Taluka' },
            { key: 'village', label: 'Village' },
        ];

        const docTablesHtml = records.map((record, idx) => {
            const rows = FIELDS.map(({ key, label }) => {
                const val = record[key] || '—';
                return `<tr>
                    <td style="border:1px solid #94a3b8;padding:7px 10px;font-weight:600;width:32%;background:#f1f5f9;color:#1e3a8a;font-size:11px;vertical-align:top;">${label}</td>
                    <td style="border:1px solid #94a3b8;padding:7px 10px;font-size:11px;color:#1e293b;vertical-align:top;line-height:1.5;">${val}</td>
                </tr>`;
            }).join('');
            return `<div style="margin-bottom:28px;page-break-inside:avoid;">
                <div style="background:#1e3a8a;color:#fff;padding:8px 14px;border-radius:4px 4px 0 0;font-size:12px;font-weight:700;">Document Record #${idx + 1}</div>
                <table style="width:100%;border-collapse:collapse;border:1px solid #94a3b8;border-top:none;"><tbody>${rows}</tbody></table>
            </div>`;
        }).join('');

        const htmlContent = `<div style="font-family:'Segoe UI',Arial,sans-serif;color:#1e293b;padding:28px 32px;max-width:780px;margin:0 auto;">
            <div style="display:flex;align-items:center;gap:18px;border-bottom:3px solid #1e3a8a;padding-bottom:14px;margin-bottom:18px;">
                <img src="${logoBase64}" alt="Mahasuchi" style="height:52px;object-fit:contain;" />
                <div>
                    <h1 style="margin:0;font-size:20px;font-weight:800;color:#1e3a8a;">Property Search Report</h1>
                    <p style="margin:3px 0 0;font-size:11px;color:#64748b;">Official Search Report — Mahasuchi</p>
                </div>
            </div>
            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:12px 16px;margin-bottom:22px;font-size:11px;color:#475569;">
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
                    <div><strong style="color:#1e293b;">District:</strong> ${d}</div>
                    <div><strong style="color:#1e293b;">Taluka:</strong> ${t}</div>
                    <div><strong style="color:#1e293b;">Village:</strong> ${v}</div>
                    <div><strong style="color:#1e293b;">Property No.:</strong> ${q}</div>
                    <div><strong style="color:#1e293b;">Generated On:</strong> ${new Date().toLocaleString('en-IN')}</div>
                    <div><strong style="color:#1e293b;">Total Records:</strong> ${records.length}</div>
                </div>
            </div>
            ${docTablesHtml}
            <div style="border-top:2px solid #e2e8f0;padding-top:10px;margin-top:10px;text-align:center;font-size:9.5px;color:#94a3b8;">
                This report is generated by Mahasuchi and is for informational reference only. Data sourced from IGR Maharashtra. © ${new Date().getFullYear()} Mahasuchi.
            </div>
        </div>`;

        const container = document.createElement('div');
        container.innerHTML = htmlContent;
        const filename = `Mahasuchi_Report_${q}.pdf`;

        return new Promise((resolve, reject) => {
            html2pdf()
                .set({
                    margin: [8, 8, 8, 8],
                    filename,
                    image: { type: 'jpeg', quality: 0.97 },
                    html2canvas: { scale: 2, useCORS: true, logging: false },
                    jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
                })
                .from(container)
                .outputPdf('blob')
                .then(blob => resolve({ blob, filename }))
                .catch(reject);
        });
    };

    // ── Proceed to Pay: Handle Lead Capture First ──────────
    const handleProceedToPay = () => {
        setPaymentError(null);
        // If we don't have lead info, show modal
        const savedLead = sessionStorage.getItem('mahasuchi_lead');
        if (!savedLead) {
            setShowLeadModal(true);
        } else {
            initiatePayment(JSON.parse(savedLead));
        }
    };

    const handleLeadSubmit = async (leadData) => {
        setShowLeadModal(false);
        sessionStorage.setItem('mahasuchi_lead', JSON.stringify(leadData));
        initiatePayment(leadData);
    };

    const initiatePayment = async (leadData) => {
        setIsPaying(true);
        try {
            // Save context for post-payment PDF generation
            sessionStorage.setItem('mahasuchi_records', JSON.stringify(filteredRecords));
            sessionStorage.setItem('mahasuchi_ctx', JSON.stringify({ district, taluka, village, query }));

            const AMOUNT = (699 * 1.18).toFixed(2);
            const txnid  = `MSC_${Date.now()}_${Math.random().toString(36).substr(2, 6).toUpperCase()}`;

            // 1. Save lead to MongoDB (Pending)
            await fetch(`${API_BASE_URL}/leads`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email: leadData.email,
                    phone: leadData.phone,
                    district, taluka, village, query,
                    txnid
                })
            });

            // 2. Initiate PayU
            const res = await fetch(`${API_BASE_URL}/payu/initiate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    amount: AMOUNT,
                    productinfo: `Property Report - ${query}`,
                    firstname: 'Customer',
                    email: leadData.email,
                    phone: leadData.phone,
                    searchQuery: query,
                    txnid // Pass txnid so backend uses the one we just saved
                })
            });

            if (!res.ok) throw new Error('Could not initiate payment');
            const params = await res.json();

            // Build and auto-submit PayU form
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = params.action;
            const fields = ['key','txnid','amount','productinfo','firstname','email','phone','surl','furl','hash','udf1'];
            fields.forEach(field => {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = field;
                input.value = params[field] || '';
                form.appendChild(input);
            });
            document.body.appendChild(form);
            form.submit();

        } catch (err) {
            console.error('[Payment]', err);
            setPaymentError(err.message || 'Something went wrong.');
            setIsPaying(false);
        }
    };


    if (loading) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
                <div className="bg-white/95 backdrop-blur-xl w-full max-w-md rounded-[2.5rem] shadow-2xl border border-slate-100 p-12 flex flex-col items-center">
                    <div className="relative mb-12 w-28 h-28 flex items-center justify-center">
                        <div className="absolute -inset-4 bg-primary/10 rounded-full blur-2xl animate-pulse"></div>
                        <div className="absolute inset-0 border-4 border-slate-100 rounded-full"></div>
                        <div className="absolute inset-0 border-4 border-t-primary border-r-blue-400 border-b-transparent border-l-transparent rounded-full animate-spin"></div>
                        <div className="absolute inset-0 flex items-center justify-center">
                            <span className="material-symbols-outlined text-primary/30 font-light text-4xl">travel_explore</span>
                        </div>
                    </div>
                    <div className="text-center space-y-4">
                        <h2 className="text-3xl font-black text-slate-800 tracking-tight">Extracting Data</h2>
                        <p className="text-slate-500 text-sm font-semibold">Interfacing with the secure <span className="text-slate-900 font-bold">MAHASUCHI</span> server block...</p>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50 pb-12 lg:pb-12 flex justify-center">
            <TopAppBar />
            <LeadCaptureModal 
                isOpen={showLeadModal} 
                onClose={() => setShowLeadModal(false)} 
                onSubmit={handleLeadSubmit} 
            />

            <div className="w-full max-w-7xl mx-auto flex flex-col pt-20 md:pt-28 px-0 md:px-6">

                {/* Header */}
                <div className="bg-gradient-to-b from-blue-50 to-white px-6 py-8 md:rounded-[2rem] text-center md:text-left shadow-sm border border-slate-200/60 mb-6 lg:mb-10 flex flex-col md:flex-row items-center md:items-end justify-between">
                    <div className="flex items-center gap-6">
                        <div className="hidden md:flex w-20 h-20 bg-primary text-white rounded-[1.5rem] shadow-xl shadow-primary/20 items-center justify-center">
                            <span className="material-symbols-outlined text-4xl">check_box</span>
                        </div>
                        <div>
                            <h2 className="text-3xl lg:text-4xl font-black text-slate-800 tracking-tight leading-tight">
                                {loading ? "Scanning Database..." : `${filteredRecords.length} Verified Records`}
                            </h2>
                            <p className="text-sm md:text-base font-bold text-azure mt-2 flex items-center gap-2 justify-center md:justify-start flex-wrap">
                                <span className="material-symbols-outlined text-[16px]">location_on</span>
                                {district} <span className="text-slate-300">•</span> {taluka} <span className="text-slate-300">•</span> {village} <span className="text-slate-300">•</span> Property No: {query}
                            </p>
                        </div>
                    </div>
                    <div className="mt-6 md:mt-0">
                        <button onClick={() => navigate('/')} className="bg-slate-100 hover:bg-slate-200 text-slate-600 font-bold py-3 px-6 rounded-full transition-colors text-sm uppercase tracking-wide flex items-center gap-2">
                            <span className="material-symbols-outlined text-[18px]">search</span>
                            New Search
                        </button>
                    </div>
                </div>

                <div className="px-4 md:px-0">
                    {loading && (
                        <div className="flex justify-center p-12">
                            <div className="animate-spin rounded-full h-12 w-12 border-4 border-azure border-t-transparent"></div>
                        </div>
                    )}

                    {error && (
                        <div className="bg-red-50 text-red-600 p-8 rounded-3xl border border-red-200 text-center font-semibold text-lg flex items-center justify-center gap-3">
                            <span className="material-symbols-outlined text-2xl">error</span>
                            {error}
                        </div>
                    )}

                    {!loading && !error && filteredRecords.length === 0 && (
                        <div className="bg-white border text-center border-slate-200 rounded-[2rem] p-12 py-20 flex flex-col items-center justify-center">
                            <div className="w-24 h-24 bg-slate-50 text-slate-300 rounded-full flex items-center justify-center mb-6">
                                <span className="material-symbols-outlined text-5xl">inventory_2</span>
                            </div>
                            <h3 className="text-2xl font-bold text-slate-800 mb-2">No Records Found</h3>
                            <p className="text-slate-500 font-medium">We couldn't find any documents matching Property No: <strong className="text-slate-800">{query}</strong>.</p>
                        </div>
                    )}

                    {/* Main Layout containing Results and Checkout */}
                    <div className={filteredRecords.length > 0 ? "grid grid-cols-1 lg:grid-cols-12 gap-8" : ""}>

                        {/* Left Side: Results Grid */}
                        <div className={filteredRecords.length > 0 ? "lg:col-span-8 xl:col-span-8" : ""}>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 lg:gap-6">
                                {filteredRecords.map((record, i) => {
                                    const dateInfo = formatDate(record.date);
                                    return (
                                        <div key={i} className="bg-white border border-slate-200 hover:border-blue-300 transition-colors rounded-2xl p-5 shadow-sm hover:shadow-md flex flex-col relative overflow-hidden">
                                            <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-blue-400 to-blue-700"></div>

                                            <div className="flex-1 pl-2">
                                                <div className="flex justify-between items-center mb-3">
                                                    <span className="bg-blue-50 text-blue-700 text-[10px] px-2 py-1 rounded font-bold uppercase tracking-widest">{record.document_type || 'Unknown'}</span>
                                                    {dateInfo && (
                                                        <div className="flex items-center gap-1 text-slate-400 text-[11px] font-semibold select-none">
                                                            <span className="material-symbols-outlined text-[14px]">calendar_today</span>
                                                            <span>{dateInfo.ddmm}/</span>
                                                            <span className="blur-sm pointer-events-none" style={{ userSelect: 'none' }}>2019</span>
                                                        </div>
                                                    )}
                                                </div>

                                                <h4 className="text-base font-black text-slate-800 block mb-1 flex items-center gap-2">
                                                    Doc No: <span className="blur-sm pointer-events-none select-none text-slate-500 font-mono">12345/2019</span>
                                                </h4>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Right Side: Checkout Panel */}
                        {filteredRecords.length > 0 && !loading && !error && (
                            <div className="lg:col-span-4 xl:col-span-4">
                                <div className="bg-white rounded-[2rem] border border-slate-200 p-6 shadow-2xl shadow-blue-900/10 sticky top-[130px]">
                                    <div className="flex flex-col items-center gap-3 mb-6 relative z-10 w-full pt-2">
                                        <div className="bg-primary text-white p-3.5 rounded-2xl mb-1 shadow-lg shadow-primary/20">
                                            <span className="material-symbols-outlined text-2xl font-bold">receipt_long</span>
                                        </div>
                                        <h3 className="text-xl font-extrabold text-slate-800 tracking-tight text-center">Summary</h3>
                                    </div>

                                    <div className="space-y-4 mb-6">
                                        <div className="flex justify-between items-center text-sm font-semibold text-slate-600">
                                            <span>Search Report Fee</span>
                                            <span className="text-slate-800">₹699</span>
                                        </div>
                                    </div>

                                    <div className="border-t border-slate-100 pt-4 mb-4 space-y-2">
                                        <div className="flex justify-between items-center text-xs font-bold text-slate-400 uppercase tracking-wider">
                                            <span>Subtotal</span>
                                            <span>₹699</span>
                                        </div>
                                        <div className="flex justify-between items-center text-xs font-bold text-slate-400 uppercase tracking-wider">
                                            <span>GST (18%)</span>
                                            <span>₹{Math.round(699 * 0.18)}</span>
                                        </div>
                                    </div>

                                    <div className="border-t border-slate-200 pt-4 mb-6">
                                        <div className="flex justify-between items-center font-black text-xl text-slate-800">
                                            <span>Total</span>
                                            <span className="text-primary">
                                                ₹{Math.round(699 * 1.18)}
                                            </span>
                                        </div>
                                        <p className="text-[10.5px] text-slate-500 font-medium mt-3 text-center leading-relaxed bg-blue-50/50 p-2.5 rounded-lg">
                                            After payment, you will receive a verified Search Report containing all the documents displayed here.
                                        </p>
                                    </div>

                                    {paymentError && (
                                        <p className="text-red-500 text-xs font-semibold text-center mb-3">{paymentError}</p>
                                    )}
                                    <button
                                        onClick={handleProceedToPay}
                                        disabled={isPaying}
                                        className="w-full bg-primary hover:bg-slate-800 text-white font-black py-4 rounded-xl shadow-xl shadow-primary/25 transition-all hover:scale-[1.02] active:scale-[0.98] text-sm uppercase tracking-widest flex items-center justify-center gap-3 disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:scale-100"
                                    >
                                        {isPaying ? (
                                            <>
                                                <span className="animate-spin material-symbols-outlined text-[20px]">sync</span>
                                                Fetching Documents...
                                            </>
                                        ) : (
                                            <>
                                                <span className="material-symbols-outlined text-[20px]">lock</span>
                                                Proceed to Pay
                                            </>
                                        )}
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>

        </div>
    );
};

// ─── Payment Success Page (PayU surl redirect) ───────────────────────────────
const PaymentSuccessPage = () => {
    const navigate = useNavigate();
    const [status, setStatus] = useState('verifying'); // verifying | generating | done | error
    const [errorMsg, setErrorMsg] = useState('');
    const [pdfBlob, setPdfBlob] = useState(null);
    const [filename, setFilename] = useState('Mahasuchi_Report.pdf');

    useEffect(() => {
        window.scrollTo(0, 0);

        // PayU POSTs form params to surl. But since React SPA cannot receive POST,
        // PayU will GET here with params in URL query string via some gateways,
        // or we rely on sessionStorage context + confirm from backend.
        // We verify by reading PayU params from URL or sessionStorage.
        const urlParams = new URLSearchParams(window.location.search);
        const txnid = urlParams.get('txnid');
        const status = urlParams.get('status');
        const hash = urlParams.get('hash');

        const doGenerate = async () => {
            try {
                // If we have PayU params, verify server-side hash
                if (txnid && hash) {
                    const params = {};
                    urlParams.forEach((v, k) => { params[k] = v; });
                    const vRes = await fetch(`${API_BASE_URL}/payu/verify`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(params)
                    });
                    const vData = await vRes.json();
                    if (!vData.verified) {
                        setStatus('error');
                        setErrorMsg('Payment verification failed. Please contact support.');
                        return;
                    }
                }

                // Retrieve records and context from sessionStorage
                const records = JSON.parse(sessionStorage.getItem('mahasuchi_records') || '[]');
                const ctx = JSON.parse(sessionStorage.getItem('mahasuchi_ctx') || '{}');

                if (!records.length || !ctx.query) {
                    setStatus('error');
                    setErrorMsg('Session expired. Please search again.');
                    return;
                }

                setStatus('generating');
                const fn = `Mahasuchi_Report_${ctx.query}.pdf`;
                setFilename(fn);

                const { blob } = await buildAndDownloadPdf_standalone(records, ctx);
                setPdfBlob(blob);

                // Auto-download
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url; a.download = fn;
                document.body.appendChild(a); a.click(); document.body.removeChild(a);

                // Clear session
                sessionStorage.removeItem('mahasuchi_records');
                sessionStorage.removeItem('mahasuchi_ctx');
                setStatus('done');

            } catch (err) {
                console.error('[PaymentSuccess]', err);
                setStatus('error');
                setErrorMsg(err.message || 'PDF generation failed.');
            }
        };

        doGenerate();
    }, []);

    const downloadAgain = () => {
        if (!pdfBlob) return;
        const url = URL.createObjectURL(pdfBlob);
        const a = document.createElement('a');
        a.href = url; a.download = filename;
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-green-50 flex items-center justify-center px-6">
            <TopAppBar />
            <div className="max-w-lg w-full mx-auto mt-20 text-center">
                <div className="bg-white rounded-[2.5rem] border border-slate-200 shadow-2xl shadow-green-900/10 p-10 flex flex-col items-center">
                    {status === 'verifying' || status === 'generating' ? (
                        <>
                            <div className="animate-spin rounded-full h-16 w-16 border-4 border-primary border-t-transparent mb-6"></div>
                            <h1 className="text-2xl font-black text-slate-800">
                                {status === 'verifying' ? 'Verifying Payment...' : 'Generating Your Report...'}
                            </h1>
                            <p className="text-slate-500 text-sm mt-2">Please wait, do not close this tab.</p>
                        </>
                    ) : status === 'done' ? (
                        <>
                            <div className="w-24 h-24 bg-green-100 text-green-600 rounded-full flex items-center justify-center mb-6 shadow-lg">
                                <span className="material-symbols-outlined text-5xl">check_circle</span>
                            </div>
                            <h1 className="text-3xl font-black text-slate-800 mb-2">Payment Successful!</h1>
                            <p className="text-slate-500 text-sm mb-2">Your verified Search Report has been downloaded.</p>
                            <p className="text-slate-400 text-xs mb-8">If download didn't start, click the button below.</p>
                            <div className="w-full bg-blue-50 rounded-2xl p-4 mb-6 text-left flex items-center gap-3">
                                <span className="material-symbols-outlined text-primary text-3xl">picture_as_pdf</span>
                                <div>
                                    <p className="text-sm font-black text-slate-800">{filename}</p>
                                    <p className="text-xs text-slate-500 mt-0.5">Official IGR Property Search Report</p>
                                </div>
                            </div>
                            <button onClick={downloadAgain} className="w-full bg-primary hover:bg-slate-800 text-white font-black py-4 rounded-xl shadow-xl shadow-primary/25 transition-all text-sm uppercase tracking-widest flex items-center justify-center gap-3 mb-4">
                                <span className="material-symbols-outlined text-[20px]">download</span>
                                Download Report Again
                            </button>
                            <button onClick={() => navigate('/', { replace: true })} className="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold py-3 rounded-xl text-sm flex items-center justify-center gap-2">
                                <span className="material-symbols-outlined text-[18px]">search</span>
                                New Search
                            </button>
                        </>
                    ) : (
                        <>
                            <div className="w-24 h-24 bg-red-100 text-red-500 rounded-full flex items-center justify-center mb-6">
                                <span className="material-symbols-outlined text-5xl">error</span>
                            </div>
                            <h1 className="text-2xl font-black text-slate-800 mb-2">Something went wrong</h1>
                            <p className="text-red-500 text-sm mb-6">{errorMsg}</p>
                            <button onClick={() => navigate(-1)} className="w-full bg-primary text-white font-bold py-3 rounded-xl text-sm mb-3">Go Back to Search</button>
                            <button onClick={() => navigate('/')} className="w-full bg-slate-100 text-slate-700 font-bold py-3 rounded-xl text-sm">New Search</button>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
};

// ─── Standalone PDF builder (used outside ResultsPage scope) ─────────────────
const buildAndDownloadPdf_standalone = async (records, ctx) => {
    const { district: d, taluka: t, village: v, query: q } = ctx;
    const logoRes = await fetch('/logo.jpeg');
    const logoBlob = await logoRes.blob();
    const logoBase64 = await new Promise((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result);
        reader.readAsDataURL(logoBlob);
    });

    const FIELDS = [
        { key: 'document_type', label: 'Document Type' },
        { key: 'registration_office', label: 'Registration Office' },
        { key: 'date', label: 'Date of Registration' },
        { key: 'seller_party', label: 'Seller / Executor Party' },
        { key: 'buyer_party', label: 'Buyer / Claimant Party' },
        { key: 'text', label: 'Property Description' },
        { key: 'district', label: 'District' },
        { key: 'taluka', label: 'Taluka' },
        { key: 'village', label: 'Village' },
    ];

    const docTablesHtml = records.map((record, idx) => {
        const rows = FIELDS.map(({ key, label }) => {
            const val = record[key] || '—';
            return `<tr>
                <td style="border:1px solid #94a3b8;padding:7px 10px;font-weight:600;width:32%;background:#f1f5f9;color:#1e3a8a;font-size:11px;vertical-align:top;">${label}</td>
                <td style="border:1px solid #94a3b8;padding:7px 10px;font-size:11px;color:#1e293b;vertical-align:top;line-height:1.5;">${val}</td>
            </tr>`;
        }).join('');
        return `<div style="margin-bottom:28px;page-break-inside:avoid;">
            <div style="background:#1e3a8a;color:#fff;padding:8px 14px;border-radius:4px 4px 0 0;font-size:12px;font-weight:700;">Document Record #${idx + 1}</div>
            <table style="width:100%;border-collapse:collapse;border:1px solid #94a3b8;border-top:none;"><tbody>${rows}</tbody></table>
        </div>`;
    }).join('');

    const htmlContent = `<div style="font-family:'Segoe UI',Arial,sans-serif;color:#1e293b;padding:28px 32px;max-width:780px;margin:0 auto;">
        <div style="display:flex;align-items:center;gap:18px;border-bottom:3px solid #1e3a8a;padding-bottom:14px;margin-bottom:18px;">
            <img src="${logoBase64}" alt="Mahasuchi" style="height:52px;object-fit:contain;" />
            <div>
                <h1 style="margin:0;font-size:20px;font-weight:800;color:#1e3a8a;">Property Search Report</h1>
                <p style="margin:3px 0 0;font-size:11px;color:#64748b;">Official Search Report — Mahasuchi</p>
            </div>
        </div>
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:12px 16px;margin-bottom:22px;font-size:11px;color:#475569;">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
                <div><strong>District:</strong> ${d}</div>
                <div><strong>Taluka:</strong> ${t}</div>
                <div><strong>Village:</strong> ${v}</div>
                <div><strong>Property No.:</strong> ${q}</div>
                <div><strong>Generated On:</strong> ${new Date().toLocaleString('en-IN')}</div>
                <div><strong>Total Records:</strong> ${records.length}</div>
            </div>
        </div>
        ${docTablesHtml}
        <div style="border-top:2px solid #e2e8f0;padding-top:10px;margin-top:10px;text-align:center;font-size:9.5px;color:#94a3b8;">
            This report is generated by Mahasuchi and is for informational reference only. © ${new Date().getFullYear()} Mahasuchi.
        </div>
    </div>`;

    const container = document.createElement('div');
    container.innerHTML = htmlContent;
    const fn = `Mahasuchi_Report_${q}.pdf`;

    return new Promise((resolve, reject) => {
        html2pdf().set({
            margin: [8, 8, 8, 8], filename: fn,
            image: { type: 'jpeg', quality: 0.97 },
            html2canvas: { scale: 2, useCORS: true, logging: false },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
        }).from(container).outputPdf('blob')
            .then(blob => resolve({ blob, filename: fn }))
            .catch(reject);
    });
};

// ─── Payment Failure Page ─────────────────────────────────────────────────────
const PaymentFailurePage = () => {
    const navigate = useNavigate();
    useEffect(() => { window.scrollTo(0, 0); }, []);

    return (
        <div className="min-h-screen bg-gradient-to-br from-red-50 via-white to-orange-50 flex items-center justify-center px-6">
            <TopAppBar />
            <div className="max-w-lg w-full mx-auto mt-20 text-center">
                <div className="bg-white rounded-[2.5rem] border border-slate-200 shadow-2xl p-10 flex flex-col items-center">
                    <div className="w-24 h-24 bg-red-100 text-red-500 rounded-full flex items-center justify-center mb-6 shadow-lg">
                        <span className="material-symbols-outlined text-5xl">cancel</span>
                    </div>
                    <h1 className="text-3xl font-black text-slate-800 mb-2 tracking-tight">Payment Failed</h1>
                    <p className="text-slate-500 font-medium text-sm mb-2">Your payment was not completed successfully.</p>
                    <p className="text-slate-400 text-xs mb-8">No amount has been deducted. Please try again.</p>
                    <button
                        onClick={() => navigate(-2)}
                        className="w-full bg-primary hover:bg-slate-800 text-white font-black py-4 rounded-xl shadow-xl text-sm uppercase tracking-widest flex items-center justify-center gap-3 mb-4 transition-all"
                    >
                        <span className="material-symbols-outlined text-[20px]">arrow_back</span>
                        Back to Search Results
                    </button>
                    <button
                        onClick={() => navigate('/', { replace: true })}
                        className="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold py-3 rounded-xl text-sm flex items-center justify-center gap-2"
                    >
                        <span className="material-symbols-outlined text-[18px]">home</span>
                        Go to Homepage
                    </button>
                </div>
            </div>
        </div>
    );
};

// ─── Success Page (legacy) ────────────────────────────────────────────────────
const SuccessPage = () => {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const filename = searchParams.get('filename') || 'Mahasuchi_Report.pdf';
    const blobUrl = searchParams.get('blobUrl');

    useEffect(() => {
        window.scrollTo(0, 0);
        if (blobUrl) triggerDownload(decodeURIComponent(blobUrl), filename);
    }, []);

    const triggerDownload = (url, name) => {
        const a = document.createElement('a');
        a.href = url; a.download = name;
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-green-50 flex items-center justify-center px-6">
            <TopAppBar />
            <div className="max-w-lg w-full mx-auto mt-20 text-center">
                <div className="bg-white rounded-[2.5rem] border border-slate-200 shadow-2xl shadow-green-900/10 p-10 flex flex-col items-center">
                    <div className="w-24 h-24 bg-green-100 text-green-600 rounded-full flex items-center justify-center mb-6 shadow-lg shadow-green-200">
                        <span className="material-symbols-outlined text-5xl">check_circle</span>
                    </div>
                    <h1 className="text-3xl font-black text-slate-800 mb-2 tracking-tight">Payment Successful!</h1>
                    <p className="text-slate-500 font-medium mb-2 text-sm">Your verified Search Report has been generated.</p>
                    <p className="text-slate-400 text-xs mb-8">Your download should have started automatically.</p>
                    <div className="w-full bg-blue-50 rounded-2xl p-5 mb-8 text-left">
                        <div className="flex items-center gap-3">
                            <span className="material-symbols-outlined text-primary text-3xl">picture_as_pdf</span>
                            <div>
                                <p className="text-sm font-black text-slate-800">{filename}</p>
                                <p className="text-xs text-slate-500 font-medium mt-0.5">Official IGR Search Report • PDF</p>
                            </div>
                        </div>
                    </div>
                    {blobUrl && (
                        <button onClick={() => triggerDownload(decodeURIComponent(blobUrl), filename)}
                            className="w-full bg-primary hover:bg-slate-800 text-white font-black py-4 rounded-xl shadow-xl shadow-primary/25 transition-all text-sm uppercase tracking-widest flex items-center justify-center gap-3 mb-4">
                            <span className="material-symbols-outlined text-[20px]">download</span>
                            Download Report Again
                        </button>
                    )}
                    <button onClick={() => navigate('/', { replace: true })} className="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold py-3 rounded-xl text-sm flex items-center justify-center gap-2">
                        <span className="material-symbols-outlined text-[18px]">search</span>
                        New Search
                    </button>
                </div>
            </div>
        </div>
    );
};

// ─── Privacy Policy Page ──────────────────────────────────────────────────────
const PrivacyPolicyPage = () => {
    useEffect(() => { window.scrollTo(0, 0); }, []);
    return (
        <div className="min-h-screen bg-slate-50">
            <TopAppBar />
            <main className="max-w-4xl mx-auto px-6 pt-32 pb-20">
                {/* Hero */}
                <div className="text-center mb-14">
                    <div className="inline-flex items-center gap-2 px-4 py-2 bg-blue-100 text-blue-800 rounded-full text-xs font-bold uppercase tracking-widest mb-6">
                        <span className="material-symbols-outlined text-sm">shield</span>
                        Legal Document
                    </div>
                    <h1 className="text-4xl lg:text-5xl font-black text-primary tracking-tight mb-4">Privacy Policy</h1>
                    <p className="text-slate-500 font-medium">Last updated: April 19, 2026</p>
                </div>

                <div className="bg-white rounded-[2rem] border border-slate-200 shadow-sm p-8 md:p-12 space-y-10 text-slate-700 leading-relaxed">

                    <section>
                        <h2 className="text-xl font-black text-primary mb-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-azure text-xl">info</span>
                            1. Introduction
                        </h2>
                        <p className="text-sm font-medium text-slate-600">
                            Welcome to <strong>Mahasuchi</strong> ("we", "our", or "us"). We are committed to protecting your personal information and
                            your right to privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when
                            you visit our platform and use our e-search services for Maharashtra land records.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-primary mb-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-azure text-xl">database</span>
                            2. Information We Collect
                        </h2>
                        <p className="text-sm font-medium text-slate-600 mb-3">We may collect the following types of information:</p>
                        <ul className="list-none space-y-2 text-sm font-medium text-slate-600">
                            {[
                                'Search queries including District, Taluka, Village, and Property Number.',
                                'Technical data such as IP address, browser type, and device information.',
                                'Usage patterns and interaction data to improve service performance.',
                                'No personally identifiable information (PII) is required to perform a search.',
                            ].map((item, i) => (
                                <li key={i} className="flex items-start gap-3">
                                    <span className="mt-1 w-2 h-2 rounded-full bg-azure flex-shrink-0"></span>
                                    {item}
                                </li>
                            ))}
                        </ul>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-primary mb-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-azure text-xl">manage_search</span>
                            3. How We Use Your Information
                        </h2>
                        <p className="text-sm font-medium text-slate-600 mb-3">We use the information we collect to:</p>
                        <ul className="list-none space-y-2 text-sm font-medium text-slate-600">
                            {[
                                'Deliver accurate and relevant land record search results.',
                                'Monitor and analyze platform usage to improve functionality.',
                                'Detect, prevent, and address technical issues or misuse.',
                                'Comply with legal obligations and government policies.',
                            ].map((item, i) => (
                                <li key={i} className="flex items-start gap-3">
                                    <span className="mt-1 w-2 h-2 rounded-full bg-azure flex-shrink-0"></span>
                                    {item}
                                </li>
                            ))}
                        </ul>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-primary mb-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-azure text-xl">share</span>
                            4. Data Sharing & Disclosure
                        </h2>
                        <p className="text-sm font-medium text-slate-600">
                            We do <strong>not</strong> sell, trade, or otherwise transfer your information to third parties. Data may be shared only
                            with trusted service providers under strict confidentiality agreements, or when required by applicable law or
                            governmental authority.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-primary mb-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-azure text-xl">lock</span>
                            5. Data Security
                        </h2>
                        <p className="text-sm font-medium text-slate-600">
                            We implement industry-standard security measures including SSL/TLS encryption, secure API endpoints, and
                            access-controlled servers to protect your data. However, no method of transmission over the Internet is 100% secure,
                            and we cannot guarantee absolute security.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-primary mb-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-azure text-xl">cookie</span>
                            6. Cookies
                        </h2>
                        <p className="text-sm font-medium text-slate-600">
                            Mahasuchi may use minimal session cookies to maintain functionality and improve user experience. These cookies do
                            not store personal information and can be disabled in your browser settings at any time.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-primary mb-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-azure text-xl">edit_note</span>
                            7. Changes to This Policy
                        </h2>
                        <p className="text-sm font-medium text-slate-600">
                            We reserve the right to update this Privacy Policy at any time. Changes will be reflected on this page with an
                            updated revision date. We encourage you to review this policy periodically.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-primary mb-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-azure text-xl">contact_mail</span>
                            8. Contact Us
                        </h2>
                        <p className="text-sm font-medium text-slate-600">
                            For any questions regarding this Privacy Policy, please reach out via the
                            <Link to="/contact" className="text-azure font-bold hover:underline ml-1">Contact page</Link>.
                        </p>
                    </section>

                </div>

                <div className="text-center mt-10">
                    <Link to="/" className="inline-flex items-center gap-2 bg-primary text-white font-bold py-3 px-8 rounded-full hover:bg-slate-800 transition-colors text-sm uppercase tracking-widest">
                        <span className="material-symbols-outlined text-[18px]">arrow_back</span>
                        Back to Home
                    </Link>
                </div>
            </main>
        </div>
    );
};

// ─── Terms & Conditions Page ──────────────────────────────────────────────────
const TermsPage = () => {
    useEffect(() => { window.scrollTo(0, 0); }, []);
    return (
        <div className="min-h-screen bg-slate-50">
            <TopAppBar />
            <main className="max-w-4xl mx-auto px-6 pt-32 pb-20">
                {/* Hero */}
                <div className="text-center mb-14">
                    <div className="inline-flex items-center gap-2 px-4 py-2 bg-blue-100 text-blue-800 rounded-full text-xs font-bold uppercase tracking-widest mb-6">
                        <span className="material-symbols-outlined text-sm">gavel</span>
                        Legal Document
                    </div>
                    <h1 className="text-4xl lg:text-5xl font-black text-primary tracking-tight mb-4">Terms &amp; Conditions</h1>
                    <p className="text-slate-500 font-medium">Last updated: April 19, 2026</p>
                </div>

                <div className="bg-white rounded-[2rem] border border-slate-200 shadow-sm p-8 md:p-12 space-y-10 text-slate-700 leading-relaxed">

                    <section>
                        <h2 className="text-xl font-black text-primary mb-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-azure text-xl">handshake</span>
                            1. Acceptance of Terms
                        </h2>
                        <p className="text-sm font-medium text-slate-600">
                            By accessing and using <strong>Mahasuchi</strong>, you agree to be bound by these Terms &amp; Conditions and all applicable
                            laws and regulations. If you do not agree with any of these terms, you are prohibited from using this platform.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-primary mb-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-azure text-xl">travel_explore</span>
                            2. Use of the Platform
                        </h2>
                        <p className="text-sm font-medium text-slate-600 mb-3">You agree to use Mahasuchi solely for lawful purposes. You must not:</p>
                        <ul className="list-none space-y-2 text-sm font-medium text-slate-600">
                            {[
                                'Use the platform for any fraudulent, misleading, or illegal activity.',
                                'Attempt to reverse-engineer, scrape, or bulk-download index data.',
                                'Interfere with or disrupt the security or integrity of our systems.',
                                'Misrepresent your identity or the purpose of your property searches.',
                            ].map((item, i) => (
                                <li key={i} className="flex items-start gap-3">
                                    <span className="mt-1 w-2 h-2 rounded-full bg-red-400 flex-shrink-0"></span>
                                    {item}
                                </li>
                            ))}
                        </ul>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-primary mb-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-azure text-xl">picture_as_pdf</span>
                            3. Data Accuracy Disclaimer
                        </h2>
                        <p className="text-sm font-medium text-slate-600">
                            Mahasuchi indexes publicly available data from the Maharashtra IGR (Inspector General of Registration) database.
                            While we strive for accuracy, we make <strong>no warranties</strong> regarding the completeness, accuracy, or timeliness
                            of the records displayed. Always verify critical property information against official government sources.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-primary mb-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-azure text-xl">copyright</span>
                            4. Intellectual Property
                        </h2>
                        <p className="text-sm font-medium text-slate-600">
                            All content, branding, software, and design elements on this platform — including the Mahasuchi name, logo, and
                            UI — are the intellectual property of Mahasuchi and are protected under applicable copyright and trademark laws.
                            Unauthorized reproduction is strictly prohibited.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-primary mb-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-azure text-xl">link_off</span>
                            5. Third-Party Links
                        </h2>
                        <p className="text-sm font-medium text-slate-600">
                            Our platform may link to external IGR PDF documents hosted on government servers. We have no control over the
                            content or availability of these third-party resources and accept no responsibility for them.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-primary mb-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-azure text-xl">block</span>
                            6. Limitation of Liability
                        </h2>
                        <p className="text-sm font-medium text-slate-600">
                            To the maximum extent permitted by law, Mahasuchi shall not be liable for any direct, indirect, incidental, or
                            consequential damages arising from your use of — or inability to use — this platform or any linked documents.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-primary mb-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-azure text-xl">account_balance</span>
                            7. Governing Law
                        </h2>
                        <p className="text-sm font-medium text-slate-600">
                            These Terms shall be governed by and construed in accordance with the laws of the <strong>Republic of India</strong>.
                            Any disputes arising out of or related to these Terms shall be subject to the exclusive jurisdiction of the
                            courts in <strong>Pune, Maharashtra</strong>.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-primary mb-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-azure text-xl">edit_note</span>
                            8. Modifications
                        </h2>
                        <p className="text-sm font-medium text-slate-600">
                            Mahasuchi reserves the right to revise these Terms at any time without prior notice. Continued use of the platform
                            after any changes constitutes your acceptance of the new Terms.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-primary mb-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-azure text-xl">contact_mail</span>
                            9. Contact
                        </h2>
                        <p className="text-sm font-medium text-slate-600">
                            For any questions regarding these Terms, please reach out via the
                            <Link to="/contact" className="text-azure font-bold hover:underline ml-1">Contact page</Link>.
                        </p>
                    </section>

                </div>

                <div className="text-center mt-10">
                    <Link to="/" className="inline-flex items-center gap-2 bg-primary text-white font-bold py-3 px-8 rounded-full hover:bg-slate-800 transition-colors text-sm uppercase tracking-widest">
                        <span className="material-symbols-outlined text-[18px]">arrow_back</span>
                        Back to Home
                    </Link>
                </div>
            </main>
        </div>
    );
};

export default function App() {
    useEffect(() => {
        // Disable right-click context menu
        const handleContextMenu = (e) => e.preventDefault();
        document.addEventListener('contextmenu', handleContextMenu);

        // Block common DevTools shortcuts
        const handleKeyDown = (e) => {
            // F12
            if (e.key === 'F12') { e.preventDefault(); return; }
            // Ctrl+Shift+I / Cmd+Option+I
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'I' || e.key === 'i')) { e.preventDefault(); return; }
            // Ctrl+Shift+J / Cmd+Option+J
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'J' || e.key === 'j')) { e.preventDefault(); return; }
            // Ctrl+Shift+C / Cmd+Option+C
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'C' || e.key === 'c')) { e.preventDefault(); return; }
            // Ctrl+U / Cmd+U (view source)
            if ((e.ctrlKey || e.metaKey) && (e.key === 'U' || e.key === 'u')) { e.preventDefault(); return; }
            // Ctrl+S / Cmd+S (save page)
            if ((e.ctrlKey || e.metaKey) && (e.key === 'S' || e.key === 's')) { e.preventDefault(); return; }
        };
        document.addEventListener('keydown', handleKeyDown);

        return () => {
            document.removeEventListener('contextmenu', handleContextMenu);
            document.removeEventListener('keydown', handleKeyDown);
        };
    }, []);

    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/loading" element={<LoadingPage />} />
                <Route path="/results" element={<ResultsPage />} />
                <Route path="/success" element={<SuccessPage />} />
                <Route path="/payment-success" element={<PaymentSuccessPage />} />
                <Route path="/payment-failure" element={<PaymentFailurePage />} />
                <Route path="/privacy" element={<PrivacyPolicyPage />} />
                <Route path="/terms" element={<TermsPage />} />
            </Routes>
        </BrowserRouter>
    );
}
