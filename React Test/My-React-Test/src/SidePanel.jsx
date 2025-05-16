import React, { useEffect, useState } from 'react';
import { initMeet } from './meet';

export default function SidePanel() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    (async () => {
      const sidePanel = await initMeet();

      // meetingId brauchen wir gleich für die Persistenz
      const { meetingId } = await sidePanel.getMeetingInfo(); // SDK-Call:contentReference[oaicite:4]{index=4}

      // bereits gespeicherte Einträge laden
      const cacheKey = `explanations_${meetingId}`;
      setItems(JSON.parse(localStorage.getItem(cacheKey) || '[]'));

      // WebSocket-Stream öffnen
      const ws = new WebSocket('wss://backend.example.com');
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        setItems((old) => {
          const updated = [...old, msg];
          localStorage.setItem(cacheKey, JSON.stringify(updated));
          return updated;
        });
      };

      // Aufräumen, wenn Meeting endet
      sidePanel.on('meeting_ended', () => localStorage.removeItem(cacheKey)); // Event Name s. SDK-Ref:contentReference[oaicite:5]{index=5}
    })();
  }, []);

  return (
    <div style={{padding:'1rem',overflowY:'auto',maxHeight:'100%'}}>
      {items.map((e) => (
        <div key={e.id} style={{marginBottom:'0.75rem',borderRadius:'12px',padding:'0.75rem',boxShadow:'0 2px 6px rgba(0,0,0,.1)'}}>
          <strong>{e.term}</strong>
          <p style={{margin:'0.25rem 0'}}>{e.explanation}</p>
        </div>
      ))}
    </div>
  );
}
