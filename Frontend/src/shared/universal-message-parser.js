// flattened copy from shared/src/universal-message-parser.js
export class UniversalMessageParser {
  static EXPLANATION_TYPES = { EXPLANATION_RESPONSE:'explanation.response', EXPLANATION_GENERATED:'explanation.generated', EXPLANATION_TERM:'explanation.term', EXPLANATION_CONCEPT:'explanation.concept', AI_EXPLANATION:'ai.explanation', TRANSCRIPTION_EXPLANATION:'transcription.explanation' };
  static parseToExplanationItem(m){ try{ if(!this.validateUniversalMessage(m)) return null; if(!this.isExplanationMessage(m)) return null; const p=m.payload||{}; const confidence = (typeof p.explanation?.confidence === 'number') ? Math.max(0, Math.min(1, p.explanation.confidence)) : null; return { id:this.generateExplanationId(m.id), title:this.extractTitle(p,m.type), content:this.extractContent(p,m.type), timestamp:this.convertTimestamp(m.timestamp), confidence, isPinned:false, isDeleted:false, createdAt:Date.now(), originalMessageId:m.id, origin:m.origin, messageType:m.type, clientId:m.client_id }; }catch(e){ console.error('Error parsing UniversalMessage to ExplanationItem:', e); return null; } }
  static isExplanationMessage(message){ const type=message.type?.toLowerCase(); if(Object.values(this.EXPLANATION_TYPES).includes(message.type)) return true; if(type?.includes('explanation')||type?.includes('explain')) return true; const payload=message.payload||{}; if(payload.explanation||payload.definition||payload.term) return true; return false; }
  static validateUniversalMessage(m){ if(!m||typeof m!=='object') return false; for(const f of ['id','type','timestamp']){ if(!m.hasOwnProperty(f)) return false; } if(typeof m.id!=='string'||typeof m.type!=='string'||typeof m.timestamp!=='number') return false; return true; }
  static extractTitle(p,t){ if(p.explanation?.title) return p.explanation.title; if(p.title) return p.title; if(p.term) return p.term; if(p.concept) return p.concept; if(p.word) return p.word; if(p.explanation?.content||p.content){ const c=p.explanation?.content||p.content; return this.extractTitleFromContent(c); } if(p.definition){ const fw=p.definition.split(' ').slice(0,4).join(' '); return fw.length>30?fw.substring(0,30)+'...':fw; } const map={'explanation.response':'KI-Erklärung','explanation.generated':'Generierte Erklärung','explanation.term':'Fachbegriff','explanation.concept':'Konzept','ai.explanation':'KI-Antwort','transcription.explanation':'Transkript-Erklärung'}; return map[t]||'Neue Erklärung'; }
  static extractTitleFromContent(content){ if(!content) return 'Neue Erklärung'; const h=content.match(/^#+ (.+)/m); if(h) return h[1]; const b=content.match(/^\*\*(.+?)\*\*/); if(b) return b[1]; const fs=content.split(/[.!?]/)[0].trim(); if(fs.length>5&&fs.length<80) return fs; const fw=content.split(' ').slice(0,5).join(' '); return fw.length>50?fw.substring(0,50)+'...':fw; }
  static extractContent(p,t){ if(p.explanation?.content) return p.explanation.content; if(p.content) return p.content; if(p.description) return p.description; if(p.definition) return p.definition; if(p.text) return p.text; if(p.term&&p.definition) return `**${p.term}**\n\n${p.definition}`; if(p.concept&&p.explanation&&p.explanation.content) return `**${p.concept}**\n\n${p.explanation.content}`; if(p.response) return p.response; if(p.answer) return p.answer; const important=['term','concept','definition','explanation','response','answer']; const found=important.filter(f=>p[f]); if(found.length>0) return found.map(f=>`**${f}:** ${p[f]}`).join('\n\n'); return `Rohdaten:\n\`\`\`json\n${JSON.stringify(p,null,2)}\n\`\`\``; }
  static convertTimestamp(u){ if(!u) return Date.now(); if(u>1000000000000) return u; return Math.floor(u*1000); }
  static generateExplanationId(id){ const clean=id.replace(/[^a-zA-Z0-9]/g,'').substring(0,8); return `exp_${Date.now()}_${clean}`; }
  static parseMultipleToExplanationItems(arr){ if(!Array.isArray(arr)) return []; return arr.map(m=>this.parseToExplanationItem(m)).filter(Boolean); }
  static parseAndAddToManager(m,manager){ const item=this.parseToExplanationItem(m); if(item&&manager){ return manager.addExplanation(item.title,item.content,item.timestamp,item.confidence); } return null; }
  static createUniversalMessageFromExplanationItem(e){
    const explanation = {
      title: e.title,
      content: e.content
    };
    if (typeof e.confidence === 'number') {
      explanation.confidence = Math.max(0, Math.min(1, e.confidence));
    }
    return {
      id: e.originalMessageId || `um_${Date.now()}_${Math.random().toString(36).slice(2,11)}`,
      type: e.messageType || 'explanation.item',
      payload: {
        explanation,
        metadata: {
          isPinned: e.isPinned,
          isDeleted: e.isDeleted,
          createdAt: e.createdAt
        }
      },
      timestamp: e.timestamp / 1000,
      origin: e.origin || 'frontend',
      destination: 'backend',
      client_id: e.clientId
    };
  }
}
