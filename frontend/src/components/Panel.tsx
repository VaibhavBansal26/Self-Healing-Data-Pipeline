import React from 'react';
export function Panel({icon,title,desc,children}:{icon:React.ReactNode;title:string;desc:string;children:React.ReactNode}){return <div className="panel"><div className="panel-head">{icon}<div><h2>{title}</h2><p>{desc}</p></div></div>{children}</div>}
