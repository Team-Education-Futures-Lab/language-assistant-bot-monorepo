import React, { useState } from 'react';
import { Plus, MessageSquare, Settings, HelpCircle, Trash2, Edit3, MoreHorizontal, User, PanelLeftOpen, PanelLeftClose } from 'lucide-react';
import appLogo from '../images/yonder_logo.png';

export default function Sidebar({
  conversations,
  activeId,
  currentPage,
  onSwitchPage,
  onGoHome,
  onNewChat,
  onSelectChat,
  onDeleteChat,
  onRenameChat,
  isOpen,
  onToggle
}) {
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');

  const handleRename = (id) => {
    const conversation = conversations.find(c => c.id === id);
    if (conversation) {
      setEditingId(id);
      setEditTitle(conversation.title);
    }
  };

  const saveRename = (id) => {
    if (editTitle.trim()) {
      onRenameChat(id, editTitle.trim());
    }
    setEditingId(null);
  };

  const handleKeyDown = (e, id) => {
    if (e.key === 'Enter') {
      saveRename(id);
    } else if (e.key === 'Escape') {
      setEditingId(null);
    }
  };

  const menuItemClass = 'group flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm text-app-text-primary transition-colors duration-200 hover:bg-gray-200';

  if (!isOpen) {
    return (
      <aside className="w-15 overflow-visible bg-app-sidebar border-r border-app-border flex flex-col transition-all duration-300 fixed left-0 top-0 bottom-0 z-50 flex-shrink-0">
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 10 }}>
          <button
            className="group relative w-10 h-10 rounded-xl border-none bg-transparent p-0 cursor-pointer overflow-hidden transition-all duration-300 hover:shadow-sm hover:scale-[1.03]"
            onClick={onToggle}
            title="Zijbalk openen"
            aria-label="Zijbalk openen"
          >
            <img
              src={appLogo}
              alt="MindLab logo"
              className="absolute inset-0 w-full h-full object-contain p-1.5 transition-all duration-300 ease-out group-hover:opacity-0 group-hover:scale-90"
            />
            <span className="absolute inset-0 flex items-center justify-center text-app-text-secondary opacity-0 scale-90 transition-all duration-300 ease-out group-hover:opacity-100 group-hover:scale-100 group-hover:bg-gray-200">
              <PanelLeftOpen size={19} />
            </span>
          </button>
        </div>
      </aside>
    );
  }

  return (
    <aside className="w-sidebar-width bg-app-sidebar border-r border-app-border flex flex-col transition-all duration-300 fixed left-0 top-0 bottom-0 z-50 flex-shrink-0">
      <div className="sticky top-0 z-20 bg-app-sidebar border-b border-app-border">
        <div className="h-14 px-2 flex items-center justify-between">
          <button
            className="h-9 rounded-lg border-none bg-transparent px-2 cursor-pointer flex items-center gap-2 hover:bg-gray-200 transition-colors duration-200"
            onClick={() => {
              if (onGoHome) {
                onGoHome();
              } else {
                onSwitchPage('chat');
              }
            }}
            title="Home"
            aria-label="Home"
          >
            <img src={appLogo} alt="MindLab logo" className="w-7 h-7 object-contain" />
            <span className="text-sm font-semibold text-app-text-primary">NT2 Chatbot</span>
          </button>

          <button
            className="h-9 w-9 rounded-lg border-none bg-transparent cursor-pointer text-app-text-secondary flex items-center justify-center hover:bg-gray-200 transition-colors duration-200"
            onClick={onToggle}
            title="Zijbalk sluiten"
            aria-label="Zijbalk sluiten"
          >
            <PanelLeftClose size={18} />
          </button>
        </div>

        <div className="px-2 pb-2 flex flex-col gap-1">
          <button
            className={menuItemClass}
            onClick={onNewChat}
          >
            <Plus size={18} className="text-app-text-secondary" />
            <span className="truncate">Nieuwe chat</span>
          </button>

          <button
            className={`${menuItemClass} ${currentPage === 'chat' ? 'bg-gray-300' : ''}`}
            onClick={() => onSwitchPage('chat')}
          >
            <MessageSquare size={18} className="text-app-text-secondary" />
            <span className="truncate">Chat</span>
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-2">
        <div className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-app-text-secondary/80">
          Chats
        </div>

        {conversations.map((conv) => (
          <div
            key={conv.id}
            className={`group flex items-center gap-2 px-2.5 py-2 mb-0.5 rounded-lg cursor-pointer transition-colors duration-200 relative overflow-hidden hover:bg-gray-200 ${conv.id === activeId ? 'bg-gray-300' : ''}`}
            onClick={() => onSelectChat(conv.id)}
          >
            <MessageSquare size={16} className="flex-shrink-0 text-app-text-secondary" />

            {editingId === conv.id ? (
              <input
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                onBlur={() => saveRename(conv.id)}
                onKeyDown={(e) => handleKeyDown(e, conv.id)}
                onClick={(e) => e.stopPropagation()}
                autoFocus
                className="flex-1 px-2 py-1 border border-app-accent rounded text-sm bg-white focus-ring"
              />
            ) : (
              <span className="flex-1 text-sm text-app-text-primary whitespace-nowrap overflow-hidden text-ellipsis">{conv.title}</span>
            )}

            {editingId !== conv.id && (
              <div className="flex gap-1 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
                <button
                  className="p-1 border-none bg-transparent cursor-pointer text-app-text-secondary rounded hover:bg-gray-300 hover:text-app-text-primary flex items-center justify-center transition-colors duration-200"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRename(conv.id);
                  }}
                  title="Hernoemen"
                >
                  <Edit3 size={14} />
                </button>
                <button
                  className="p-1 border-none bg-transparent cursor-pointer text-app-text-secondary rounded hover:bg-gray-300 hover:text-app-text-primary flex items-center justify-center transition-colors duration-200"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteChat(conv.id);
                  }}
                  title="Verwijderen"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="p-2 border-t border-app-border flex flex-col gap-1 bg-app-sidebar">
        <button className={menuItemClass}>
          <Settings size={18} className="text-app-text-secondary" />
          <span>Instellingen</span>
        </button>

        <button className={menuItemClass}>
          <HelpCircle size={18} className="text-app-text-secondary" />
          <span>Hulp</span>
        </button>

        <div className="mt-1">
          <button className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg border-none bg-transparent cursor-pointer hover:bg-gray-200 transition-colors duration-200 text-left">
            <div className="w-6 h-6 rounded-full bg-app-accent text-white flex items-center justify-center shrink-0">
              <User size={14} />
            </div>
            <span className="flex-1 text-sm font-medium text-app-text-primary">Gebruiker</span>
            <MoreHorizontal size={16} className="text-app-text-secondary" />
          </button>
        </div>
      </div>
    </aside>
  );
}
