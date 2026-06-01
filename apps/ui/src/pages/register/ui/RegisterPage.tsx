import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { z } from 'zod';

import { Button } from '@shared/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@shared/ui/card';
import { Input } from '@shared/ui/input';
import { Label } from '@shared/ui/label';
import { registerUser } from '@features/auth-register';

const schema = z.object({
  email: z.string().email('Невірний формат email'),
  password: z.string().min(6, 'Мінімум 6 символів'),
  full_name: z.string().optional(),
});
type FormValues = z.infer<typeof schema>;

export default function RegisterPage() {
  const { register, handleSubmit, formState: { errors, isSubmitting } } =
    useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    try {
      await registerUser(values.email, values.password, values.full_name || undefined);
      toast.success('Акаунт створено');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Не вдалося зареєструватися');
    }
  };

  return (
    <div className="flex justify-center mt-12">
      <Card className="w-full max-w-md">
        <CardHeader><CardTitle>Реєстрація</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" autoComplete="email" {...register('email')} />
              {errors.email && <span className="text-sm text-destructive">{errors.email.message}</span>}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="full_name">Ім'я (необов'язково)</Label>
              <Input id="full_name" type="text" autoComplete="name" {...register('full_name')} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Пароль</Label>
              <Input id="password" type="password" autoComplete="new-password" {...register('password')} />
              {errors.password && <span className="text-sm text-destructive">{errors.password.message}</span>}
            </div>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Створення…' : 'Зареєструватися'}
            </Button>
            <p className="text-sm text-muted-foreground text-center">
              Вже є акаунт?{' '}
              <Link to="/login" className="text-primary underline-offset-4 hover:underline">Увійти</Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
