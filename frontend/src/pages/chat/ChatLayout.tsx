import React from 'react';

const ChatLayout = () => {
    return (
        <div className="flex h-screen bg-background">
            {/* Sidebar */}
            <div className="w-64 border-r p-4 hidden md:block">
                <h2 className="font-bold text-lg mb-4">Chat History</h2>
                <div className="space-y-2">
                     <div className="p-2 hover:bg-muted rounded cursor-pointer">Previous Chat 1</div>
                     <div className="p-2 hover:bg-muted rounded cursor-pointer">Previous Chat 2</div>
                </div>
            </div>
            
            {/* Main Chat Area */}
            <div className="flex-1 flex flex-col">
                <div className="flex-1 p-4 overflow-auto">
                    {/* Messages */}
                    <div className="space-y-4">
                        <div className="flex justify-end">
                             <div className="bg-primary text-white p-3 rounded-lg max-w-[80%]">User Question</div>
                        </div>
                        <div className="flex justify-start">
                             <div className="bg-muted p-3 rounded-lg max-w-[80%]">AI Response</div>
                        </div>
                    </div>
                </div>
                
                {/* Input Area */}
                <div className="p-4 border-t">
                    <div className="flex gap-2">
                        <input className="flex-1 border rounded p-2" placeholder="Type a message..." />
                        <button className="bg-primary text-white px-4 py-2 rounded">Send</button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ChatLayout;
