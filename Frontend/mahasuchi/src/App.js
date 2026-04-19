import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link, useNavigate, useLocation, useSearchParams } from 'react-router-dom';

const API_BASE_URL = 'http://127.0.0.1:8000/api';

// --- Shared Components ---
const TopAppBar = () => {
    return (
        <header className="fixed w-full top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-slate-200/60 shadow-sm dark:bg-slate-900/95 dark:border-slate-800 transition-all">
            <div className="flex flex-col items-center py-2 bg-primary">
                <span className="text-[10px] sm:text-xs font-bold text-white/80 uppercase tracking-[0.25em]">India's first AI-powered e-search</span>
            </div>
            <nav className="flex justify-between items-center px-5 py-4 max-w-7xl mx-auto w-full">
                <Link to="/" className="flex items-center gap-3 md:gap-4 hover:opacity-90 transition-opacity">
                    <div className="w-10 h-10 md:w-12 md:h-12 bg-primary rounded-xl flex items-center justify-center shadow-md shadow-primary/20">
                        <span className="material-symbols-outlined text-white text-2xl md:text-[28px]">account_balance</span>
                    </div>
                    <div className="flex flex-col">
                        <span className="text-xl md:text-2xl font-black tracking-tight text-primary dark:text-white leading-none">Mahasuchi</span>
                        <span className="text-[10px] md:text-xs font-bold text-azure uppercase tracking-widest mt-1">E-RECORDS</span>
                    </div>
                </Link>
                <div className="flex items-center gap-4">
                    <div className="hidden lg:flex items-center gap-6 pr-4 border-r border-slate-200 mr-2 text-sm font-bold text-slate-600">
                        <Link to="/" className="hover:text-azure transition-colors">Home</Link>
                        <Link to="/about" className="hover:text-azure transition-colors">About Us</Link>
                        <Link to="/contact" className="hover:text-azure transition-colors">Help Center</Link>
                    </div>
                    <button className="flex items-center justify-center border border-slate-200 bg-white dark:bg-slate-800 dark:border-slate-700 rounded-full w-12 h-12 hover:bg-slate-50 hover:shadow-md hover:scale-105 active:scale-95 transition-all shadow-sm">
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
        if(!selectedDistrict || !selectedTaluka || !selectedVillage || !query) {
            alert("Please fill all fields.");
            return;
        }
        const params = new URLSearchParams({
            district: selectedDistrict,
            taluka: selectedTaluka,
            village: selectedVillage,
            query: query
        });
        navigate(`/loading?${params.toString()}`);
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
            <main className="flex-1 pt-[100px] lg:pt-[130px] pb-32 px-4 md:px-8">
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
                                    <label className="block text-[11px] font-bold uppercase tracking-[0.1em] text-slate-500 px-1 transition-colors group-hover:text-primary">Property No. (Numeric)</label>
                                    <div className="relative transition-all border border-slate-200 rounded-xl bg-slate-50 hover:border-blue-300 focus-within:border-blue-500 focus-within:ring-4 focus-within:ring-blue-500/10 overflow-hidden">
                                        <input 
                                            className="w-full bg-transparent border-0 focus:ring-0 text-slate-800 font-bold text-sm py-4 pl-12 pr-10 outline-none" 
                                            placeholder="Ex: 128" 
                                            required 
                                            type="text" 
                                            value={query}
                                            onChange={handleQueryChange}
                                        />
                                        <div className="absolute inset-y-0 left-0 flex items-center pl-4 text-slate-400">
                                            <span className="material-symbols-outlined text-[20px]">pin</span>
                                        </div>
                                        {query && (
                                            <div className="absolute inset-y-0 right-0 flex items-center pr-4 text-green-500">
                                                <span className="material-symbols-outlined text-[20px] font-bold">check_circle</span>
                                            </div>
                                        )}
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
                        <Link to="#" className="hover:text-white transition-colors">Privacy</Link>
                        <Link to="#" className="hover:text-white transition-colors">Terms</Link>
                        <Link to="#" className="hover:text-white transition-colors">API Portal</Link>
                        <Link to="#" className="hover:text-white transition-colors">Contact</Link>
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
            <BottomNavBar />
        </div>
    );
};

// Loading and Results code remaining essentially identical but polished slightly 
const LoadingPage = () => {
    const navigate = useNavigate();
    const location = useLocation();

    useEffect(() => {
        const timer = setTimeout(() => {
            navigate(`/results${location.search}`);
        }, 2000);
        return () => clearTimeout(timer);
    }, [navigate, location]);

    return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4 selection:bg-azure selection:text-white">
            <div className="bg-white/95 backdrop-blur-xl w-full max-w-md rounded-[2.5rem] shadow-[0_30px_60px_-15px_rgba(0,0,0,0.1)] border border-slate-100 p-12 lg:p-16 flex flex-col items-center">
                <div className="relative mb-12 w-28 h-28 flex items-center justify-center">
                    <div className="absolute -inset-4 bg-azure/10 rounded-full blur-2xl animate-pulse"></div>
                    <div className="absolute inset-0 border-4 border-slate-100 rounded-full"></div>
                    <div className="absolute inset-0 border-4 border-t-azure border-r-blue-400 border-b-transparent border-l-transparent rounded-full animate-spin"></div>
                    <div className="absolute inset-3 border-2 border-slate-100 border-l-azure border-b-transparent border-t-transparent border-r-transparent rounded-full animate-spin-slow"></div>
                    <div className="absolute inset-0 flex items-center justify-center">
                        <span className="material-symbols-outlined text-azure/30 font-light text-4xl">travel_explore</span>
                    </div>
                </div>
                <div className="text-center space-y-8">
                    <div className="space-y-2">
                        <h2 className="text-3xl font-black text-slate-800 tracking-tight">Extracting Data</h2>
                        <div className="flex justify-center mt-4">
                            <div className="h-1.5 w-12 bg-azure rounded-full"></div>
                        </div>
                    </div>
                    <p className="text-slate-500 text-sm xl:text-base leading-relaxed px-2 font-semibold">
                        Interfacing with the secure <span className="text-slate-900 font-bold">MAHASUCHI</span> server block...
                    </p>
                </div>
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

    useEffect(() => {
        fetch(`${API_BASE_URL}/search?district=${encodeURIComponent(district)}&taluka=${encodeURIComponent(taluka)}&village=${encodeURIComponent(village)}&query=${encodeURIComponent(query)}`)
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    setError(data.error);
                } else {
                    setRecords(data.results || []);
                }
                setLoading(false);
            })
            .catch(err => {
                console.error(err);
                setError("Failed to fetch records");
                setLoading(false);
            });
    }, [district, taluka, village, query]);

    return (
        <div className="min-h-screen bg-slate-50 pb-20 lg:pb-12 pt-0 md:pt-8 flex justify-center">
            <TopAppBar />
            <div className="w-full max-w-7xl mx-auto flex flex-col pt-16 md:pt-24 px-0 md:px-6">
                
                {/* Header */}
                <div className="bg-gradient-to-b from-blue-50 to-white px-6 py-8 md:rounded-[2rem] text-center md:text-left shadow-sm border border-slate-200/60 mb-6 lg:mb-10 flex flex-col md:flex-row items-center md:items-end justify-between">
                    <div className="flex items-center gap-6">
                        <div className="hidden md:flex w-20 h-20 bg-primary text-white rounded-[1.5rem] shadow-xl shadow-primary/20 items-center justify-center">
                            <span className="material-symbols-outlined text-4xl">check_box</span>
                        </div>
                        <div>
                            <h2 className="text-3xl lg:text-4xl font-black text-slate-800 tracking-tight leading-tight">
                                {loading ? "Scanning Database..." : `${records.length} Verified Records`}
                            </h2>
                            <p className="text-sm md:text-base font-bold text-azure mt-2 flex items-center gap-2 justify-center md:justify-start flex-wrap">
                                <span className="material-symbols-outlined text-[16px]">location_on</span>
                                {district} <span className="text-slate-300">•</span> {taluka} <span className="text-slate-300">•</span> {village}
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
                    
                    {!loading && !error && records.length === 0 && (
                        <div className="bg-white border text-center border-slate-200 rounded-[2rem] p-12 py-20 flex flex-col items-center justify-center">
                            <div className="w-24 h-24 bg-slate-50 text-slate-300 rounded-full flex items-center justify-center mb-6">
                                <span className="material-symbols-outlined text-5xl">inventory_2</span>
                            </div>
                            <h3 className="text-2xl font-bold text-slate-800 mb-2">No Records Found</h3>
                            <p className="text-slate-500 font-medium">We couldn't find any documents matching Property Survey No: <strong className="text-slate-800">{query}</strong>.</p>
                        </div>
                    )}

                    {/* Responsive Grid for Desktop */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 lg:gap-6">
                        {records.map((record, i) => (
                            <div key={i} className="bg-white border border-slate-200 hover:border-blue-300 transition-colors rounded-2xl p-5 shadow-sm hover:shadow-md flex flex-col relative overflow-hidden">
                                <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-blue-400 to-blue-700"></div>
                                
                                <div className="flex-1 pl-2">
                                    <div className="flex justify-between items-center mb-3">
                                        <span className="bg-blue-50 text-blue-700 text-[10px] px-2 py-1 rounded font-bold uppercase tracking-widest">{record.document_type || 'Unknown'}</span>
                                        <div className="flex items-center gap-1 text-slate-400 text-[11px] font-semibold">
                                            <span className="material-symbols-outlined text-[14px]">calendar_today</span>
                                            {record.date}
                                        </div>
                                    </div>
                                    
                                    <h4 className="text-base font-black text-slate-800 block mb-1">Doc No: {record.document_number}</h4>
                                    
                                    <div className="text-xs text-slate-600 leading-relaxed italic mb-4 line-clamp-4 bg-slate-50 p-3 rounded-lg border border-slate-100">
                                        "{record.text}"
                                    </div>
                                </div>
                                
                                <div className="mt-auto pt-3 border-t border-slate-100 pl-2">
                                    {record.pdf_link ? (
                                        <a href={record.pdf_link} target="_blank" rel="noopener noreferrer" 
                                           className="w-full bg-slate-800 hover:bg-slate-900 text-white font-bold py-2.5 px-4 rounded-lg transition-all flex justify-center items-center gap-2 text-xs uppercase tracking-wider shadow-sm">
                                            <span className="material-symbols-outlined text-[16px]">download</span>
                                            Download PDF
                                        </a>
                                    ) : (
                                        <button disabled className="w-full bg-slate-100 text-slate-400 font-bold py-2.5 px-4 rounded-lg cursor-not-allowed flex justify-center items-center gap-2 text-xs uppercase tracking-wider">
                                            <span className="material-symbols-outlined text-[16px]">lock</span>
                                            Not Available
                                        </button>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
            <BottomNavBar />
        </div>
    );
};

export default function App() {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/loading" element={<LoadingPage />} />
                <Route path="/results" element={<ResultsPage />} />
            </Routes>
        </BrowserRouter>
    );
}
