export function JsonBlock({data}:{data:any}) { return <pre className="json-block">{JSON.stringify(data, null, 2)}</pre>; }
