import {Info, PlayCircle, Eye} from 'lucide-react';

type Props = {
  title: string;
  purpose: string;
  shows: string[];
  test: string;
};

export function SectionInfo({title, purpose, shows, test}: Props){
  return <div className="section-info-card">
    <div className="section-info-main">
      <div className="section-info-icon"><Info size={19}/></div>
      <div>
        <span className="eyebrow">What this section does</span>
        <h2>{title}</h2>
        <p>{purpose}</p>
      </div>
    </div>
    <div className="section-info-grid">
      <div>
        <b><Eye size={15}/> You should see</b>
        <ul>{shows.map((s)=><li key={s}>{s}</li>)}</ul>
      </div>
      <div>
        <b><PlayCircle size={15}/> How to test</b>
        <p>{test}</p>
      </div>
    </div>
  </div>;
}
