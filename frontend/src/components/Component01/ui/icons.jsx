// Local, dependency-free line-icon set. Keeps Component01 portable in the group repo.
const paths = {
 leaf:<><path d="M20 4C12 4 4 8 4 16c0 2 2 4 4 4C16 20 20 12 20 4Z"/><path d="M4 20c4-6 8-9 14-12"/></>,
 arrow:<><path d="M5 12h14M13 6l6 6-6 6"/></>,
 up:<><path d="M7 17 17 7M8 7h9v9"/></>,
 check:<><circle cx="12" cy="12" r="9"/><path d="m7.5 12 3 3 6-6"/></>,
 alert:<><circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 17h.01"/></>,
 warn:<><path d="M11 3a2 2 0 0 1 2 0l9 16a2 2 0 0 1-2 3H4a2 2 0 0 1-2-3L11 3Z"/><path d="M12 9v5M12 18h.01"/></>,
 refresh:<><path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.5 9a7 7 0 0 1 12-2l2.5 5M4 12l2.5 5A7 7 0 0 0 18.5 15"/></>,
 camera:<><path d="M4 7h4l2-3h4l2 3h4a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2Z"/><circle cx="12" cy="13" r="4"/></>,
 upload:<><path d="M12 16V4m-4 4 4-4 4 4"/><path d="M20 16v4H4v-4"/></>,
 spark:<><path d="m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5L12 2Z"/></>,
 board:<><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 10h18M10 10v11"/></>,
 chart:<><path d="M3 20h18M5 17l5-6 4 3 5-9"/><circle cx="5" cy="17" r="1"/><circle cx="19" cy="5" r="1"/></>,
 map:<><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M15 3v18M3 9h18M3 15h18"/></>,
 location:<><path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="3"/></>,
 weather:<><path d="M7 18H5a4 4 0 0 1 0-8h2a6 6 0 0 1 12 1 3.5 3.5 0 0 1 0 7H7Z"/><path d="M8 3V1M3 6 1 4"/></>,
 rain:<><path d="M5 17a4 4 0 0 1 0-8h2a6 6 0 0 1 12 1 3.5 3.5 0 0 1 0 7H5"/><path d="m8 19-1 3m6-3-1 3m6-3-1 3"/></>,
 droplet:<><path d="M12 2S5 11 5 15a7 7 0 0 0 14 0c0-4-7-13-7-13Z"/></>,
 thermo:<><path d="M10 14V5a2 2 0 0 1 4 0v9a5 5 0 1 1-4 0Z"/><path d="M12 9v9"/></>,
 wind:<><path d="M3 8h12a3 3 0 1 0-3-3M3 12h17a3 3 0 1 1-3 3M3 16h9a3 3 0 1 1-3 3"/></>,
 shield:<><path d="M12 2 21 6v6c0 6-5 9-9 10-4-1-9-4-9-10V6l9-4Z"/><path d="m8 12 3 3 5-6"/></>,
 clipboard:<><rect x="5" y="5" width="14" height="17" rx="2"/><rect x="9" y="2" width="6" height="5" rx="1"/><path d="M9 12h6M9 16h6"/></>,
 save:<><path d="M4 3h13l4 4v14H3V3h1Z"/><path d="M7 3v7h10V3M7 21v-8h10v8"/></>,
 eye:<><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></>,
 bell:<><path d="M5 17h14l-2-3V9a5 5 0 0 0-10 0v5l-2 3ZM10 20a2 2 0 0 0 4 0"/></>,
 calendar:<><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 2v6M16 2v6M3 10h18M8 15h2m4 0h2"/></>,
 plus:<><path d="M12 4v16M4 12h16"/></>,
 menu:<><path d="M3 6h18M3 12h18M3 18h18"/></>,
 close:<><path d="M5 5l14 14M19 5 5 19"/></>,
 down:<><path d="m6 9 6 6 6-6"/></>,
 care:<><path d="M12 21s-9-6-9-12a5 5 0 0 1 9-3 5 5 0 0 1 9 3c0 6-9 12-9 12Z"/></>,
}
const make = (type) => function SvgIcon({size=20,strokeWidth=1.8,...props}){return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[type] || paths.leaf}</svg>}
export const Leaf=make('leaf')
export const ArrowRight=make('arrow')
export const ArrowUpRight=make('up')
export const CheckCircle2=make('check')
export const CircleCheck=make('check')
export const AlertCircle=make('alert')
export const AlertTriangle=make('warn')
export const RefreshCw=make('refresh')
export const RefreshCcw=make('refresh')
export const Camera=make('camera')
export const UploadCloud=make('upload')
export const Sparkles=make('spark')
export const LayoutDashboard=make('board')
export const ChartNoAxesCombined=make('chart')
export const TrendingUp=make('chart')
export const Map=make('map')
export const MapPinned=make('location')
export const CloudSun=make('weather')
export const CloudRain=make('rain')
export const Thermometer=make('thermo')
export const Droplets=make('droplet')
export const Wind=make('wind')
export const ShieldCheck=make('shield')
export const ShieldAlert=make('shield')
export const ClipboardList=make('clipboard')
export const ClipboardCheck=make('clipboard')
export const Save=make('save')
export const Eye=make('eye')
export const Bell=make('bell')
export const BellRing=make('bell')
export const CalendarClock=make('calendar')
export const CalendarCheck=make('calendar')
export const Menu=make('menu')
export const X=make('close')
export const ChevronDown=make('down')
export const Activity=make('chart')
export const Sprout=make('leaf')
export const HeartHandshake=make('care')
export const Stethoscope=make('care')
export const CircleHelp=make('alert')
