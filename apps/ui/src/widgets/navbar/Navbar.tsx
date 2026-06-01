import { NavLink } from 'react-router-dom';
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
import { useAuthStore } from '@shared/zustand/useAuthStore';
import { NAV_SECTIONS } from '@shared/config/routes';
import { cn } from '@/lib/utils';

export default function Navbar() {
  const user = useAuthStore((s) => s.user);
  const clearToken = useAuthStore((s) => s.clearToken);

  if (!user) return null;

  return (
    <nav className="flex flex-wrap items-center gap-x-4 gap-y-2 mb-8">
      <div className="flex flex-wrap items-center gap-1">
        {NAV_SECTIONS.map((s) => (
          <NavLink
            key={s.to}
            to={s.to}
            className={({ isActive }) =>
              cn(
                'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
              )
            }
          >
            {s.label}
          </NavLink>
        ))}
      </div>

      <div className="ml-auto flex items-center gap-2">
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
            <DropdownMenuItem onClick={clearToken} className="text-destructive">
              <LogOut className="h-4 w-4 mr-2" />
              Вийти
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </nav>
  );
}
