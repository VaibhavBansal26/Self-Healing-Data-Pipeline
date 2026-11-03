import React from 'react';
export function StatCard({title,value,icon,color}:{title:string;value:any;icon:React.ReactNode;color?:string}) { return <div className={`stat-card ${color||''}`}><div className="stat-icon">{icon}</div><div><div className="stat-title">{title}</div><div className="stat-value">{value ?? 0}</div></div></div>; }
