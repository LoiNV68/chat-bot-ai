import React from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardTitle, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';

const DocumentManager = () => {
    return (
        <div className="p-8 space-y-8">
            <h1 className="text-3xl font-bold">Document Management</h1>
            
            <Card>
                <CardHeader>
                    <CardTitle>Upload New Document</CardTitle>
                </CardHeader>
                <CardContent className="flex gap-4">
                    <Input type="file" />
                    <Button>Upload</Button>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Existing Documents</CardTitle>
                </CardHeader>
                <CardContent>
                    <table className="w-full text-left">
                        <thead>
                            <tr className="border-b">
                                <th className="p-2">Filename</th>
                                <th className="p-2">Version</th>
                                <th className="p-2">Status</th>
                                <th className="p-2">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr className="border-b">
                                <td className="p-2">Policy_2024.pdf</td>
                                <td className="p-2">v1</td>
                                <td className="p-2 text-green-600">Active</td>
                                <td className="p-2">
                                    <Button size="sm" variant="destructive">Delete</Button>
                                </td>
                            </tr>
                            <tr className="border-b">
                                <td className="p-2">Schedule_Term1.xlsx</td>
                                <td className="p-2">v2</td>
                                <td className="p-2 text-green-600">Active</td>
                                <td className="p-2">
                                    <Button size="sm" variant="destructive">Delete</Button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </CardContent>
            </Card>
        </div>
    );
};

export default DocumentManager;
