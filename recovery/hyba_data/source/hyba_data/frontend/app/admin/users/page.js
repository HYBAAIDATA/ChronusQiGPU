'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, Plus, Trash2, Edit, Shield, Users } from 'lucide-react'

export default function UserManagementPage() {
  const router = useRouter()
  const { user, isAdmin, getAuthHeaders } = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    max_blocks: 1000,
    max_dollar_value: 10000,
    max_hashrate_ehs: 100,
    role: 'user'
  })

  useEffect(() => {
    if (!isAdmin()) {
      router.push('/')
      return
    }
    fetchUsers()
  }, [])

  const fetchUsers = async () => {
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const response = await fetch(`${API_URL}/api/users`, {
        headers: getAuthHeaders()
      })

      if (!response.ok) {
        throw new Error('Failed to fetch users')
      }

      const data = await response.json()
      setUsers(data.users || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleCreateUser = async (e) => {
    e.preventDefault()
    setError('')

    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const response = await fetch(`${API_URL}/api/users`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(formData)
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to create user')
      }

      setShowCreateForm(false)
      setFormData({
        email: '',
        password: '',
        max_blocks: 1000,
        max_dollar_value: 10000,
        max_hashrate_ehs: 100,
        role: 'user'
      })
      fetchUsers()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleDeleteUser = async (email) => {
    if (!confirm(`Are you sure you want to delete ${email}?`)) return

    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const response = await fetch(`${API_URL}/api/users/${email}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      })

      if (!response.ok) {
        throw new Error('Failed to delete user')
      }

      fetchUsers()
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2 flex items-center gap-2">
            <Shield className="w-8 h-8" />
            User Management
          </h1>
          <p className="text-slate-400">Manage user accounts and permissions (Admin Only)</p>
        </div>

        {error && (
          <Alert variant="destructive" className="mb-6 bg-red-500/10 border-red-500/20">
            <AlertDescription className="text-red-400">{error}</AlertDescription>
          </Alert>
        )}

        <Card className="bg-slate-900/50 backdrop-blur-xl border-purple-500/20 mb-6">
          <CardHeader>
            <div className="flex justify-between items-center">
              <div>
                <CardTitle className="text-white flex items-center gap-2">
                  <Users className="w-5 h-5" />
                  Users ({users.length})
                </CardTitle>
                <CardDescription className="text-slate-400">
                  All users with hybamine.com email addresses
                </CardDescription>
              </div>
              <Button
                onClick={() => setShowCreateForm(!showCreateForm)}
                className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700"
              >
                <Plus className="w-4 h-4 mr-2" />
                Create User
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {showCreateForm && (
              <form onSubmit={handleCreateUser} className="mb-6 p-4 bg-slate-800/50 rounded-lg border border-slate-700">
                <h3 className="text-white font-semibold mb-4">Create New User</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label className="text-slate-300">Email (hybamine.com)</Label>
                    <Input
                      type="email"
                      placeholder="user@hybamine.com"
                      value={formData.email}
                      onChange={(e) => setFormData({...formData, email: e.target.value})}
                      className="bg-slate-800/50 border-slate-700 text-white"
                      required
                    />
                  </div>
                  <div>
                    <Label className="text-slate-300">Password</Label>
                    <Input
                      type="password"
                      placeholder="••••••••"
                      value={formData.password}
                      onChange={(e) => setFormData({...formData, password: e.target.value})}
                      className="bg-slate-800/50 border-slate-700 text-white"
                      required
                    />
                  </div>
                  <div>
                    <Label className="text-slate-300">Max Blocks</Label>
                    <Input
                      type="number"
                      value={formData.max_blocks}
                      onChange={(e) => setFormData({...formData, max_blocks: parseInt(e.target.value)})}
                      className="bg-slate-800/50 border-slate-700 text-white"
                    />
                  </div>
                  <div>
                    <Label className="text-slate-300">Max Dollar Value ($)</Label>
                    <Input
                      type="number"
                      step="0.01"
                      value={formData.max_dollar_value}
                      onChange={(e) => setFormData({...formData, max_dollar_value: parseFloat(e.target.value)})}
                      className="bg-slate-800/50 border-slate-700 text-white"
                    />
                  </div>
                  <div>
                    <Label className="text-slate-300">Max Hashrate (EH/s)</Label>
                    <Input
                      type="number"
                      step="0.1"
                      value={formData.max_hashrate_ehs}
                      onChange={(e) => setFormData({...formData, max_hashrate_ehs: parseFloat(e.target.value)})}
                      className="bg-slate-800/50 border-slate-700 text-white"
                    />
                  </div>
                  <div>
                    <Label className="text-slate-300">Role</Label>
                    <select
                      value={formData.role}
                      onChange={(e) => setFormData({...formData, role: e.target.value})}
                      className="w-full bg-slate-800/50 border border-slate-700 text-white rounded-md px-3 py-2"
                    >
                      <option value="user">User</option>
                      <option value="admin">Admin</option>
                    </select>
                  </div>
                </div>
                <div className="flex gap-2 mt-4">
                  <Button type="submit" className="bg-gradient-to-r from-purple-600 to-blue-600">
                    Create User
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setShowCreateForm(false)}
                    className="border-slate-600 text-slate-300 hover:bg-slate-800"
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            )}

            <Table>
              <TableHeader>
                <TableRow className="border-slate-700">
                  <TableHead className="text-slate-300">Email</TableHead>
                  <TableHead className="text-slate-300">Role</TableHead>
                  <TableHead className="text-slate-300">Max Blocks</TableHead>
                  <TableHead className="text-slate-300">Max Value ($)</TableHead>
                  <TableHead className="text-slate-300">Max Hashrate (EH/s)</TableHead>
                  <TableHead className="text-slate-300">Status</TableHead>
                  <TableHead className="text-slate-300">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((user) => (
                  <TableRow key={user.email} className="border-slate-800">
                    <TableCell className="text-white">{user.email}</TableCell>
                    <TableCell>
                      <span className={`px-2 py-1 rounded-full text-xs ${
                        user.role === 'admin' 
                          ? 'bg-purple-500/20 text-purple-400' 
                          : 'bg-blue-500/20 text-blue-400'
                      }`}>
                        {user.role}
                      </span>
                    </TableCell>
                    <TableCell className="text-slate-300">
                      {user.max_blocks === Infinity ? '∞' : user.max_blocks}
                    </TableCell>
                    <TableCell className="text-slate-300">
                      {user.max_dollar_value === Infinity ? '∞' : `$${user.max_dollar_value.toLocaleString()}`}
                    </TableCell>
                    <TableCell className="text-slate-300">{user.max_hashrate_ehs} EH/s</TableCell>
                    <TableCell>
                      <span className={`px-2 py-1 rounded-full text-xs ${
                        user.is_active 
                          ? 'bg-green-500/20 text-green-400' 
                          : 'bg-red-500/20 text-red-400'
                      }`}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </TableCell>
                    <TableCell>
                      {user.role !== 'admin' && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteUser(user.email)}
                          className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
