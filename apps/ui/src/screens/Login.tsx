import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { Link, useLocation } from 'react-router-dom';
import { toast } from 'sonner';
import { z } from 'zod';

import { Button } from '@/components/ui/button.tsx';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card.tsx';
import { Input } from '@/components/ui/input.tsx';
import { Label } from '@/components/ui/label.tsx';
import { useAuthStore } from '@shared/zustand/useAuthStore';
import { ApiError } from '@shared/api/error';
import { API_BASE_URL } from '@shared/config/env';
import * as authApi from '@/api/auth';
import type { User } from '@shared/types/user';

const schema = z.object({
  email: z.string().email('Невірний формат email'),
  password: z.string().min(1, 'Введіть пароль'),
});

type FormValues = z.infer<typeof schema>;

export default function Login() {
  const location = useLocation();
  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? '/services';

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    try {
      const { access_token } = await authApi.login(values.email, values.password);
      // Fetch user with the fresh token before writing to the store, then
      // set token + user + redirect destination in ONE atomic update.
      const res = await fetch(`${API_BASE_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${access_token}` },
      });
      if (!res.ok) throw new ApiError(res.status, 'Не вдалося отримати дані профілю');
      const user: User = await res.json();
      useAuthStore.getState().loginSuccess(access_token, user, from);
      toast.success('Вхід виконано');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Не вдалося увійти');
    }
  };

  return (
    <div className="flex justify-center mt-12">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Вхід</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" autoComplete="email" {...register('email')} />
              {errors.email && <span className="text-sm text-destructive">{errors.email.message}</span>}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Пароль</Label>
              <Input id="password" type="password" autoComplete="current-password" {...register('password')} />
              {errors.password && (
                <span className="text-sm text-destructive">{errors.password.message}</span>
              )}
            </div>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Вхід…' : 'Увійти'}
            </Button>
            <p className="text-sm text-muted-foreground text-center">
              Немає акаунта?{' '}
              <Link to="/register" className="text-primary underline-offset-4 hover:underline">
                Зареєструватися
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
