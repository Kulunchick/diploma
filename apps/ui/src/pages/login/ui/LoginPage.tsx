import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { Link, useLocation } from 'react-router-dom';
import { toast } from 'sonner';
import { z } from 'zod';

import { Button } from '@shared/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@shared/ui/card';
import { Input } from '@shared/ui/input';
import { Label } from '@shared/ui/label';
import { loginUser } from '@features/auth-login';

const schema = z.object({
  email: z.string().email('Невірний формат email'),
  password: z.string().min(1, 'Введіть пароль'),
});
type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  const location = useLocation();
  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;

  const { register, handleSubmit, formState: { errors, isSubmitting } } =
    useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    try {
      await loginUser(values.email, values.password, from);
      toast.success('Вхід виконано');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Не вдалося увійти');
    }
  };

  return (
    <div className="flex justify-center mt-12">
      <Card className="w-full max-w-md">
        <CardHeader><CardTitle>Вхід</CardTitle></CardHeader>
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
              {errors.password && <span className="text-sm text-destructive">{errors.password.message}</span>}
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
