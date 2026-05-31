import { Link } from 'react-router-dom';
import { ChevronDown, LogOut } from 'lucide-react';

import { Button } from '@/components/ui/button.tsx';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu.tsx';
import { useAuth } from '@/auth/AuthContext';

const SYSTEM_SECTIONS = [
  { to: '/services', label: 'Сервіси' },
  { to: '/service-groups', label: 'Групи сервісів' },
  { to: '/providers', label: 'Провайдери' },
  { to: '/planning', label: 'Планові дані' },
  { to: '/formations', label: 'Формування пакетів' },
];

export default function Navbar() {
  const { user, logout } = useAuth();

  return (
    <nav className="flex flex-wrap justify-center items-center gap-4 mb-8">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button className="gap-1">
            Інформаційна система
            <ChevronDown className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          {SYSTEM_SECTIONS.map((s) => (
            <DropdownMenuItem key={s.to} asChild>
              <Link to={s.to}>{s.label}</Link>
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      <div className="ml-auto flex items-center gap-2">
        {user ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" className="gap-1">
                {user.email}
                <ChevronDown className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>{user.full_name || user.email}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={logout} className="text-destructive">
                <LogOut className="h-4 w-4 mr-2" />
                Вийти
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <>
            <Link to="/login" className="text-sm text-primary underline-offset-4 hover:underline">
              Увійти
            </Link>
            <span className="text-muted-foreground">/</span>
            <Link to="/register" className="text-sm text-primary underline-offset-4 hover:underline">
              Зареєструватися
            </Link>
          </>
        )}
      </div>
    </nav>
  );
}
